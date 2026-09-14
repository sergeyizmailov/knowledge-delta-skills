"""MCP companion mode: validate before a tool call, audit after one.

The official TikTok MCP server is the primary way to operate an ad account. It
is also unguarded: it will happily create a campaign with ``operation_status``
defaulting to ENABLE, or accept a USD-shaped budget on a JPY account, because it
is a faithful wrapper over endpoints that behave that way.

This module is the guard rail around it, and it works **with no token and no
network** — which matters, because an operator who cannot register a developer
app has MCP access and nothing else.

    preflight  spec            -> exact arguments to hand each MCP tool
    audit      spec + MCP JSON -> what the platform actually stored, and what is wrong
"""

from __future__ import annotations

from decimal import Decimal

from . import errors as err_mod
from . import money, spec as spec_mod

# Lifecycle step -> (MCP tool name, underlying endpoint). Source: TikTok's
# "Available tools in TikTok for Business MCP Server", fetched 2026-09-14.
TOOL_MAP = {
    "whoami": ("auth_advertiser_get", "/oauth2/advertiser/get/"),
    "advertiser": ("advertiser_info_get", "/advertiser/info/"),
    "balance": ("advertiser_balance_get", "/advertiser/balance/get/"),
    "pixels": ("pixel_list_get", "/pixel/list/"),
    "identities": ("identity_get", "/identity/get/"),
    "video_upload": ("file_video_ad_upload", "/file/video/ad/upload/"),
    "video_status": ("file_video_ad_info_get", "/file/video/ad/info/"),
    "image_upload": ("file_image_ad_upload", "/file/image/ad/upload/"),
    "campaign_create": ("campaign_create", "/campaign/create/"),
    "adgroup_create": ("adgroup_create", "/adgroup/create/"),
    "ad_create": ("ad_create", "/ad/create/"),
    "campaign_read": ("campaign_get", "/campaign/get/"),
    "adgroup_read": ("adgroup_get", "/adgroup/get/"),
    "ad_read": ("ad_get", "/ad/get/"),
    "campaign_status": ("campaign_status_update", "/campaign/status/update/"),
    "adgroup_status": ("adgroup_status_update", "/adgroup/status/update/"),
    "ad_status": ("ad_status_update", "/ad/status/update/"),
    "preview": ("creative_ads_preview_create", "/creative/ads_preview/create/"),
    "review": ("ad_review_info_get", "/ad/review_info/"),
    "report": ("report_integrated_get", "/report/integrated/get/"),
    "bid_recommend": ("tool_bid_recommend", "/tool/bid/recommend/"),
    "audience_size": ("ad_audience_size_estimate", "/ad/audience_size/estimate/"),
    "vbo_status": ("tool_vbo_status_check", "/tool/vbo_status/"),
    "url_validate": ("tool_url_validate", "/tool/url_validate/"),
    "diagnose": ("tiktok_ads_diagnosis_agent", None),
}


def preflight(spec_obj, profile):
    """Validate a spec offline and emit the arguments for each MCP tool call.

    Returns the calls in execution order. Every create call carries
    ``operation_status: "DISABLE"`` — MCP will not add it for you, and TikTok's
    default is ENABLE.
    """
    plan = spec_mod.normalize(spec_obj, profile)   # raises SpecError on anything invalid
    currency = plan["currency"]

    calls = [{
        "step": 1,
        "tool": TOOL_MAP["campaign_create"][0],
        "endpoint": TOOL_MAP["campaign_create"][1],
        "arguments": plan["campaign"],
        "returns": "campaign_id",
        "note": "operation_status DISABLE is deliberate — TikTok defaults to ENABLE.",
    }]

    step = 2
    for ag in plan["adgroups"]:
        calls.append({
            "step": step,
            "tool": TOOL_MAP["adgroup_create"][0],
            "endpoint": TOOL_MAP["adgroup_create"][1],
            "arguments": dict(ag["payload"], campaign_id="<campaign_id from step 1>"),
            "returns": "adgroup_id",
            "note": "attribution window locks at creation and cannot be changed afterwards.",
        })
        step += 1
        calls.append({
            "step": step,
            "tool": TOOL_MAP["ad_create"][0],
            "endpoint": TOOL_MAP["ad_create"][1],
            "arguments": spec_mod.ad_payload(
                plan["advertiser_id"], f"<adgroup_id from step {step - 1}>", ag["creatives"]),
            "returns": "ad_ids",
            "note": "video_id must be READY — poll file_video_ad_info_get first (error 40901).",
        })
        step += 1

    return {
        "ok": True,
        "advertiser_id": plan["advertiser_id"],
        "currency": currency,
        "timezone": plan["timezone"],
        "cbo": plan["cbo"],
        "budgets": spec_mod.budget_summary(plan),
        "total_daily": money.describe(spec_mod.total_daily(plan), currency),
        "calls": calls,
        "after": [
            f"Read every object back with {TOOL_MAP['campaign_read'][0]}, "
            f"{TOOL_MAP['adgroup_read'][0]}, {TOOL_MAP['ad_read'][0]}.",
            "Save those responses to a file and run: ttops audit --spec <spec> --actual <file>",
            "Only then enable, bottom-up: ads, ad groups, campaign.",
        ],
    }


# ---------------------------------------------------------------------------
# audit — diff what MCP actually created against what you asked for
# ---------------------------------------------------------------------------

# Same rule as the token path: a field the spec sends is a field that must be
# compared. Anything sent and never diffed is a silent drift channel.
_CAMPAIGN_FIELDS = ("objective_type", "budget_mode", "budget", "budget_optimize_on",
                    "special_industries", "app_promotion_type", "virtual_objective_type",
                    "sales_destination", "campaign_product_source", "campaign_type",
                    "catalog_enabled", "is_search_campaign", "app_id", "operation_status")
_ADGROUP_FIELDS = ("optimization_goal", "optimization_event", "secondary_optimization_event",
                   "billing_event", "bid_type", "bid_price", "conversion_bid_price",
                   "deep_bid_type", "deep_cpa_bid", "roas_bid", "budget_mode", "budget",
                   "pacing", "placement_type", "placements", "schedule_type",
                   "schedule_start_time", "schedule_end_time", "pixel_id",
                   "promotion_type", "promotion_target_type", "product_source",
                   "product_set_id", "catalog_id", "store_id", "app_id",
                   "identity_id", "identity_type",
                   "click_attribution_window", "view_attribution_window",
                   "engaged_view_attribution_window", "attribution_event_count",
                   "comment_disabled", "video_download_disabled", "share_disabled",
                   "audience_ids", "excluded_audience_ids", "targeting_expansion",
                   "skip_learning_phase", "is_hfss", "is_lhf_compliance",
                   "operation_status")
_AD_FIELDS = ("ad_format", "identity_type", "identity_id", "video_id", "image_ids",
              "ad_text", "call_to_action", "call_to_action_id", "landing_page_url",
              "display_name", "page_id", "tiktok_item_id", "music_id",
              "deeplink", "deeplink_type", "impression_tracking_url",
              "click_tracking_url", "utm_params", "item_group_ids",
              "creative_authorized", "creative_auto_enhancement_strategy_list",
              "operation_status")


# Keys that hold a collection of objects rather than one object. A combined file
# may carry several of them at once, so every match is merged — returning on the
# first one silently drops the rest, which is the difference between catching a
# live campaign and missing it.
_CONTAINER_KEYS = ("list", "data", "campaign", "campaigns", "adgroup", "adgroups",
                   "ad", "ads", "results")
_ID_KEYS = ("campaign_id", "adgroup_id", "ad_id")


def _rows(blob):
    """Accept whatever the agent pasted: a tool result, its data, a list, one object,
    or a hand-assembled file holding all three levels at once."""
    if blob is None:
        return []
    if isinstance(blob, list):
        out = []
        for item in blob:
            out.extend(_rows(item))
        return out
    if not isinstance(blob, dict):
        return []

    # An object that carries an ID is a leaf, even if it also has nested keys.
    if any(k in blob for k in _ID_KEYS):
        return [blob]

    out = []
    for key in _CONTAINER_KEYS:
        if key in blob:
            out.extend(_rows(blob[key]))
    if out:
        return out
    # Unrecognised wrapper: descend into dict/list values rather than give up.
    for value in blob.values():
        if isinstance(value, (dict, list)):
            out.extend(_rows(value))
    return out


def _classify(rows):
    """Split a flat pile of objects by which ID field they carry."""
    buckets = {"campaign": [], "adgroup": [], "ad": []}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if "ad_id" in row:
            buckets["ad"].append(row)
        elif "adgroup_id" in row:
            buckets["adgroup"].append(row)
        elif "campaign_id" in row:
            buckets["campaign"].append(row)
    return buckets


def _same(want, have):
    if isinstance(want, (list, tuple)) and isinstance(have, (list, tuple)):
        return sorted(map(str, want)) == sorted(map(str, have))
    try:
        return abs(float(want) - float(have)) < 0.005
    except (TypeError, ValueError):
        pass
    return str(want) == str(have)


def audit(actual, spec_obj=None, profile=None, *, expect_paused=True):
    """Check objects the MCP server created. ``spec_obj`` is optional.

    Without a spec this still runs every danger check that does not need one —
    which is the common case when a campaign was built conversationally.
    """
    rows = _rows(actual)
    if not rows:
        return {"ok": False,
                "reason": "No objects found. Paste the result of campaign_get / adgroup_get / "
                          "ad_get — the whole tool response is fine."}

    buckets = _classify(rows)
    findings = []
    currency = (profile or {}).get("currency") or (spec_obj or {}).get("currency")

    def flag(severity, obj, field, detail, sent=None, got=None):
        item = {"severity": severity, "object": obj, "field": field, "detail": detail}
        if sent is not None:
            item["expected"] = sent
        if got is not None:
            item["on_platform"] = got
        findings.append(item)

    # --- danger checks that need no spec -----------------------------------
    for level, objs in buckets.items():
        for row in objs:
            oid = row.get(f"{level}_id") or row.get("id") or "?"
            label = f"{level}:{oid}"

            status = row.get("operation_status")
            if expect_paused and status and status != "DISABLE":
                flag("SPENDING", label, "operation_status",
                     "Object is not paused. TikTok defaults to ENABLE — if you did not "
                     "deliberately enable this, it is live and spending right now.",
                     "DISABLE", status)

            secondary = row.get("secondary_status") or row.get("status")
            if secondary:
                info = err_mod.explain_status(secondary)
                sev = {"BLOCKED": "BLOCKED", "MONEY": "MONEY", "REVIEW": "INFO",
                       "LIVE": "INFO", "INFO": "INFO", "UNKNOWN": "WARN"}[info["severity"]]
                if info["severity"] == "LIVE" and expect_paused:
                    sev = "SPENDING"
                flag(sev, label, "secondary_status", info["action"], got=secondary)

            if currency and row.get("budget") not in (None, ""):
                lvl = "campaign" if level == "campaign" else "adgroup"
                store = row.get("product_source") in ("STORE", "SHOWCASE") or \
                    row.get("campaign_product_source") == "STORE"
                try:
                    money.validate(row["budget"], currency, lvl, store_product_source=store)
                except money.BudgetError as exc:
                    flag("MONEY", label, "budget", str(exc), got=row["budget"])

            if level == "adgroup" and not row.get("schedule_start_time"):
                flag("WARN", label, "schedule_start_time",
                     "No start time read back. A past start time does not error — it starts now.")

    # --- diff against the spec, when there is one --------------------------
    checked = {"campaign": 0, "adgroup": 0, "ad": 0}
    if spec_obj and profile:
        plan = spec_mod.normalize(spec_obj, profile)

        if not buckets["campaign"]:
            flag("MISSING", "campaign", "_exists",
                 "The spec describes a campaign and none was read back. Either it was "
                 "never created, or your read-back does not cover it — an audit can only "
                 "judge what you paste in. Read campaign_get before trusting a green.")

        for row in buckets["campaign"]:
            label = f"campaign:{row.get('campaign_id')}"
            checked["campaign"] += 1
            for field in _CAMPAIGN_FIELDS:
                if field not in plan["campaign"] or field == "operation_status":
                    continue
                want, have = plan["campaign"][field], row.get(field)
                if have is None or have == "":
                    flag("UNCONFIRMED", label, field,
                         "The read-back does not report this field, so it could not be "
                         "verified either way.", want, None)
                    continue
                if not _same(want, have):
                    flag("DRIFT", label, field,
                         "The platform stored something other than what you asked for. "
                         "TikTok drops unknown keys and fills enum defaults silently.",
                         want, have)

        by_name = {r.get("adgroup_name"): r for r in buckets["adgroup"]}
        for ag in plan["adgroups"]:
            row = by_name.get(ag["_name"])
            if row is None:
                flag("MISSING", f"adgroup:{ag['_name']}", "_exists",
                     "In the spec but not in what you pasted back. Either it was never "
                     "created or the read did not cover it.")
                continue
            checked["adgroup"] += 1
            label = f"adgroup:{row.get('adgroup_id')}"
            for field in _ADGROUP_FIELDS:
                if field not in ag["payload"] or field == "operation_status":
                    continue
                want, have = ag["payload"][field], row.get(field)
                if have is None or have == "":
                    flag("UNCONFIRMED", label, field,
                         "The read-back does not report this field, so it could not be "
                         "verified either way. Several of these are permanent — check the "
                         "attribution windows and video_download_disabled in Ads Manager.",
                         want, None)
                    continue
                if not _same(want, have):
                    flag("DRIFT", label, field,
                         "Stored value differs from the spec.", want, have)

        # Diff each ad against the creative the spec described. Matching on
        # (adgroup_id, ad_name) because ad ids are assigned by TikTok, not by us.
        wanted_ads = {}
        for ag in plan["adgroups"]:
            row = by_name.get(ag["_name"])
            ag_id = str(row.get("adgroup_id")) if row else None
            for creative in ag["creatives"]:
                wanted_ads[(ag_id, creative["ad_name"])] = creative
        for row in buckets["ad"]:
            sent = wanted_ads.get((str(row.get("adgroup_id")), row.get("ad_name")))
            label = f"ad:{row.get('ad_id')}"
            if sent is None:
                flag("DRIFT", label, "_unexpected",
                     "This ad is in the read-back but not in the spec. Either the spec is "
                     "not the one that built it, or the ad group holds ads nobody planned.",
                     "not in this plan", row.get("ad_name"))
                continue
            for field in _AD_FIELDS:
                if field not in sent or field == "operation_status":
                    continue
                want, have = sent[field], row.get(field)
                if have is None or have == "":
                    flag("UNCONFIRMED", label, field,
                         "The read-back does not report this field, so it could not be "
                         "verified either way.", want, None)
                    continue
                if not _same(want, have):
                    flag("DRIFT", label, field,
                         "The ad does not point where the spec said. Destination, creative "
                         "asset and identity are where spend actually goes.", want, have)

        expected_ads = sum(len(a["creatives"]) for a in plan["adgroups"])
        checked["ad"] = len(buckets["ad"])
        if checked["ad"] < expected_ads:
            flag("MISSING", "ads", "_count",
                 f"Spec describes {expected_ads} ad(s); {checked['ad']} were read back. "
                 "Either creatives failed at create time or the read-back does not cover "
                 "them. Do not enable a campaign whose ads you have not seen.")
        elif checked["ad"] > expected_ads:
            flag("WARN", "ads", "_count",
                 f"Spec describes {expected_ads} ad(s); {checked['ad']} were read back. "
                 "The ad group holds ads this spec did not create — check what else is in it.")

    # A read-back that covers nothing, or only part of the tree, must never read as
    # "everything is fine" — the audit judges exactly what it was given and no more.
    total_rows = sum(len(v) for v in buckets.values())
    if total_rows == 0:
        flag("MISSING", "readback", "_empty",
             "No campaign, ad group or ad was found in the input. Nothing was checked. "
             "Paste the results of campaign_get / adgroup_get / ad_get.")
    else:
        absent = [lvl for lvl in ("campaign", "adgroup", "ad") if not buckets[lvl]]
        if absent and not (spec_obj and profile):
            flag("WARN", "readback", "_coverage",
                 "Read-back covers only " +
                 ", ".join(f"{lvl} ({len(buckets[lvl])})" for lvl in ("campaign", "adgroup", "ad")
                           if buckets[lvl]) +
                 ". Nothing was checked at: " + ", ".join(absent) +
                 ". A clean result here says nothing about the levels you did not paste.")

    worst = None
    for level in ("SPENDING", "MONEY", "BLOCKED", "MISSING", "DRIFT",
                  "UNCONFIRMED", "WARN", "INFO"):
        if any(f["severity"] == level for f in findings):
            worst = level
            break

    safe = worst in (None, "INFO")
    return {
        "ok": safe,
        "objects_seen": {k: len(v) for k, v in buckets.items()},
        "compared_against_spec": bool(spec_obj and profile),
        "checked": checked,
        "worst_severity": worst,
        "findings": findings,
        "verdict": _verdict(worst, buckets),
    }


def _verdict(worst, buckets):
    """Say what was actually established. A warning about coverage is not a
    warning about spend, and conflating the two teaches the reader to skim."""
    seen = ", ".join(f"{k}: {len(v)}" for k, v in buckets.items())
    if worst in (None, "INFO"):
        return (f"No problems in what was read back ({seen}). Safe to review previews "
                "and then enable bottom-up — provided that is every object in the campaign.")
    if worst == "SPENDING":
        return ("Something is LIVE that should not be. Pause it first, diagnose second. "
                "Do not enable anything else until this is resolved.")
    if worst in ("MONEY", "BLOCKED", "MISSING"):
        return ("DO NOT ENABLE until these are resolved. Money, review and missing-object "
                "findings all mean the campaign is not in the state you think it is.")
    if worst == "DRIFT":
        return ("TikTok stored something other than what was asked for. Decide whether each "
                "difference is acceptable before enabling — some fields cannot be changed "
                "after creation.")
    if worst == "UNCONFIRMED":
        return (f"Nothing contradicts the spec in what was read back ({seen}), but some fields "
                "were not reported by the platform and could not be verified either way. "
                "Check the permanent ones — attribution windows, video_download_disabled — in "
                "Ads Manager before enabling.")
    return (f"Nothing dangerous found in what was read back ({seen}), but this audit is "
            "incomplete or has open questions. Resolve them before treating it as a green.")


def total_daily_if_enabled(spec_obj, profile):
    """What this spec will spend per day once enabled — the number to confirm aloud."""
    plan = spec_mod.normalize(spec_obj, profile)
    return money.describe(spec_mod.total_daily(plan), plan["currency"]), Decimal(
        str(spec_mod.total_daily(plan)))
