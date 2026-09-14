"""Launch spec: validation and normalisation into TikTok v1.3 payloads.

The agent writes a spec. This module turns it into payloads. Nothing else
hand-assembles a TikTok request body — a new shape means extending this file and
its tests, not improvising JSON at the call site.
"""

from __future__ import annotations

from decimal import Decimal

from . import money

# ---------------------------------------------------------------------------
# Enums, copied from TikTok's Enumerations page (doc 1737174886619138) and the
# Advertising objective page (doc 1737585562434561). Fetched 2026-09-14.
# ---------------------------------------------------------------------------

OBJECTIVES = {
    "REACH", "TRAFFIC", "VIDEO_VIEWS", "ENGAGEMENT", "LEAD_GENERATION",
    "APP_PROMOTION", "WEB_CONVERSIONS", "PRODUCT_SALES", "RF_REACH",
}

# Values that exist in the enum but are read-only filters, not creatable goals.
FILTER_ONLY_GOALS = {"GMV", "PURCHASES", "INITIATE_CHECKOUTS"}

OPTIMIZATION_GOALS = {
    "CLICK", "CONVERT", "INSTALL", "IN_APP_EVENT", "SHOW", "REACH",
    "LEAD_GENERATION", "PREFERRED_LEAD", "CONVERSATION", "FOLLOWERS",
    "PAGE_VISIT", "VALUE", "AUTOMATIC_VALUE_OPTIMIZATION", "ENGAGED_VIEW",
    "ENGAGED_VIEW_FIFTEEN", "TRAFFIC_LANDING_PAGE_VIEW", "DESTINATION_VISIT",
    "MT_LIVE_ROOM", "PRODUCT_CLICK_IN_LIVE",
}

DEPRECATED_GOALS = {
    "VIDEO_VIEW": "deprecated",
    "CONVERSION_LEADS": "deprecated",
    "PROFILE_VIEWS": "to be deprecated — use PAGE_VISIT",
}

# Goals that auto-populate optimization_event; setting it yourself errors or is ignored.
GOALS_OWNING_EVENT = {
    "ENGAGED_VIEW", "ENGAGED_VIEW_FIFTEEN", "CONVERSATION",
    "DESTINATION_VISIT", "TRAFFIC_LANDING_PAGE_VIEW",
}

BID_TYPES = {"BID_TYPE_NO_BID", "BID_TYPE_CUSTOM"}
BILLING_EVENTS = {"CPC", "CPM", "CPV", "OCPM", "GD"}

# TikTok: "For each optimization goal, you need to manually specify the
# corresponding billing_event simultaneously." The mapping is not a suggestion —
# a mismatched pair is rejected at /adgroup/create/. Table from doc 1739499616346114.
GOAL_BILLING_EVENT = {
    "CLICK": "CPC", "PAGE_VISIT": "CPC",
    "CONVERT": "OCPM", "INSTALL": "OCPM", "IN_APP_EVENT": "OCPM",
    "TRAFFIC_LANDING_PAGE_VIEW": "OCPM", "LEAD_GENERATION": "OCPM",
    "CONVERSATION": "OCPM", "FOLLOWERS": "OCPM", "VALUE": "OCPM",
    "AUTOMATIC_VALUE_OPTIMIZATION": "OCPM", "PRODUCT_CLICK_IN_LIVE": "OCPM",
    "MT_LIVE_ROOM": "OCPM", "DESTINATION_VISIT": "OCPM",
    "SHOW": "CPM", "REACH": "CPM",
    "ENGAGED_VIEW": "CPV", "ENGAGED_VIEW_FIFTEEN": "CPV",
}

PACING_MODES = {"PACING_MODE_SMOOTH", "PACING_MODE_FAST"}

# Objectives where TikTok does NOT require promotion_type.
PROMOTION_TYPE_EXEMPT_OBJECTIVES = {"REACH", "VIDEO_VIEWS", "ENGAGEMENT"}

# `APP_ANDRIOD` is TikTok's own spelling in the enum tables; both are accepted here.
PROMOTION_TYPES = {
    "APP_ANDROID", "APP_ANDRIOD", "APP_IOS", "MINI_APP", "MINI_GAME", "GAME",
    "WEBSITE", "LEAD_GENERATION", "LEAD_GEN_CLICK_TO_TT_DIRECT_MESSAGE",
    "LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE", "LEAD_GEN_CLICK_TO_CALL",
    "WEBSITE_OR_DISPLAY", "TIKTOK_SHOP", "VIDEO_SHOPPING", "LIVE_SHOPPING",
    "PSA_PRODUCT",
}

# Attribution windows. TikTok: once set, these cannot be updated — so getting them
# wrong at create time means rebuilding the ad group, not editing it.
CLICK_ATTRIBUTION_WINDOWS = {"OFF", "ONE_DAY", "SEVEN_DAYS", "FOURTEEN_DAYS",
                             "TWENTY_EIGHT_DAYS"}
VIEW_ATTRIBUTION_WINDOWS = {"OFF", "ONE_DAY", "SEVEN_DAYS"}
ENGAGED_VIEW_ATTRIBUTION_WINDOWS = {"ONE_DAY", "SEVEN_DAYS"}
ATTRIBUTION_EVENT_COUNTS = {"UNSET", "EVERY", "ONCE"}
BUDGET_MODES = {
    "BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL",
    "BUDGET_MODE_DYNAMIC_DAILY_BUDGET", "BUDGET_MODE_INFINITE",
}
PLACEMENTS = {"PLACEMENT_TIKTOK", "PLACEMENT_PANGLE", "PLACEMENT_GLOBAL_APP_BUNDLE"}
PLACEMENT_TYPES = {"PLACEMENT_TYPE_AUTOMATIC", "PLACEMENT_TYPE_NORMAL"}
SCHEDULE_TYPES = {"SCHEDULE_FROM_NOW", "SCHEDULE_START_END"}
AD_FORMATS = {"SINGLE_IMAGE", "SINGLE_VIDEO", "CAROUSEL_ADS", "LIVE_CONTENT"}
IDENTITY_TYPES = {"CUSTOMIZED_USER", "AUTH_CODE", "TT_USER", "BC_AUTH_TT"}
SPECIAL_INDUSTRIES = {"HOUSING", "EMPLOYMENT", "CREDIT"}

# Campaign-level budget modes are constrained by whether CBO is on.
CBO_ON_MODES = {"BUDGET_MODE_TOTAL", "BUDGET_MODE_DYNAMIC_DAILY_BUDGET", "BUDGET_MODE_DAY"}
CBO_OFF_MODES = {"BUDGET_MODE_INFINITE", "BUDGET_MODE_TOTAL", "BUDGET_MODE_DAY"}

# Campaign daily budget mode forbids an ad-group LIFETIME budget.
INCOMPATIBLE = {("BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL")}

SCHEMA_VERSION = "ttops.spec/v1"


class SpecError(ValueError):
    pass


def _require(cond, message, errors):
    if not cond:
        errors.append(message)
    return cond


def validate(spec, profile):
    """Validate a spec against a workspace profile. Returns a list of errors."""
    errors = []
    currency = profile["currency"]

    if spec.get("schema") != SCHEMA_VERSION:
        errors.append(f"schema must be {SCHEMA_VERSION!r}, got {spec.get('schema')!r}")

    # The spec must name the currency it was written for, and it must match the
    # account. This is the single guard that stops a USD template spending 100x
    # on a JPY account.
    spec_currency = spec.get("currency")
    if not spec_currency:
        errors.append(
            "spec.currency is required. Write the account's currency into the spec so a "
            "mismatch is caught locally instead of at 100x on a no-decimal currency."
        )
    elif spec_currency.upper() != currency.upper():
        errors.append(
            f"spec.currency {spec_currency!r} != account currency {currency!r} "
            f"(profile {profile['_name']!r}). Refusing: budgets would be wrong."
        )

    camp = spec.get("campaign") or {}
    _require(camp.get("campaign_name"), "campaign.campaign_name is required", errors)
    objective = camp.get("objective_type")
    if not _require(objective, "campaign.objective_type is required", errors):
        objective = None
    elif objective not in OBJECTIVES:
        errors.append(
            f"campaign.objective_type {objective!r} is not a TikTok objective. "
            f"Valid: {', '.join(sorted(OBJECTIVES))}. Note there is no SALES enum — "
            "the Sales objective is WEB_CONVERSIONS/PRODUCT_SALES + virtual_objective_type."
        )
    if objective == "RF_REACH":
        errors.append(
            "campaign.objective_type RF_REACH (Reach & Frequency) is not supported by ttops. "
            "Two reasons, both structural: TikTok requires operation_status ENABLE (or omitted) "
            "for R&F campaigns, which is incompatible with the create-paused guarantee this "
            "tool is built on; and R&F ad groups use /adgroup/rf/create/, a different endpoint "
            "with its own reservation flow. Build R&F in Ads Manager or through the MCP rf_* "
            "tools, with the spend approved before creation rather than after."
        )

    # Shapes ttops deliberately does not build. Each has its own endpoints and its own
    # activation semantics; emitting an ordinary campaign payload for them produces
    # either a rejection or — worse — a different product than the one planned.
    if camp.get("campaign_type") in ("SMART_PERFORMANCE_CAMPAIGN", "SMART_PLUS_CAMPAIGN"):
        errors.append(
            "campaign.campaign_type names a Smart+ campaign. ttops does not build Smart+ — it "
            "uses /smart_plus/* endpoints with their own review and preview flow. Use the MCP "
            "smart_plus_campaign_create / smart_plus_adgroup_create / smart_plus_ad_create tools, "
            "and note the ≤1 write per 5 seconds per ad limit."
        )
    if camp.get("objective_type") == "PRODUCT_SALES" and \
            camp.get("campaign_product_source") == "STORE":
        errors.append(
            "PRODUCT_SALES with campaign_product_source STORE is a TikTok Shop sales campaign. "
            "ttops does not build GMV Max, which is the path TikTok has been steering Shop sales "
            "to since 2025 (see tiktok-ads playbooks/ecommerce). Use the MCP "
            "campaign_gmv_max_create / gmv_max_bid_recommend_get tools. If you have confirmed this "
            "account can still run an ordinary Shop-sales campaign and you want one, create it "
            "through MCP directly and audit the read-back with `ttops audit`."
        )

    if camp.get("virtual_objective_type") and not camp.get("sales_destination"):
        errors.append("campaign.sales_destination is required when virtual_objective_type is set")
    if objective == "APP_PROMOTION" and not camp.get("app_promotion_type"):
        errors.append("campaign.app_promotion_type is required when objective_type is APP_PROMOTION")
    if objective == "PRODUCT_SALES" and not camp.get("campaign_product_source"):
        errors.append("campaign.campaign_product_source is required when objective_type is PRODUCT_SALES")

    for ind in camp.get("special_industries") or []:
        if ind not in SPECIAL_INDUSTRIES:
            errors.append(f"campaign.special_industries has unknown value {ind!r}")
    if "special_industries" not in camp:
        errors.append(
            "campaign.special_industries must be declared explicitly — [] if genuinely none. "
            "An omitted field on a housing/employment/credit offer is a policy violation, "
            "not a default."
        )

    cbo = bool(camp.get("budget_optimize_on"))
    adgroups = spec.get("adgroups") or []
    if not adgroups:
        errors.append("spec.adgroups must contain at least one ad group")

    store_src = camp.get("campaign_product_source") == "STORE"

    # -- campaign budget ---------------------------------------------------
    c_mode = camp.get("budget_mode")
    if c_mode and c_mode not in BUDGET_MODES:
        errors.append(f"campaign.budget_mode {c_mode!r} invalid")
    if cbo:
        if c_mode not in CBO_ON_MODES:
            errors.append(f"With CBO on, campaign.budget_mode must be one of {sorted(CBO_ON_MODES)}")
        if camp.get("budget") is None:
            errors.append("With CBO on, campaign.budget is required")
        if any(ag.get("budget") is not None for ag in adgroups):
            errors.append(
                "With CBO on, ad-group budgets are ignored by TikTok. Remove them from the "
                "spec so the plan says what will actually happen."
            )
    else:
        if c_mode and c_mode not in CBO_OFF_MODES:
            errors.append(f"With CBO off, campaign.budget_mode must be one of {sorted(CBO_OFF_MODES)}")
        if c_mode in ("BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL") and camp.get("budget") is None:
            errors.append(f"campaign.budget is required when budget_mode is {c_mode}")

    if camp.get("budget") is not None and spec_currency:
        try:
            money.validate(camp["budget"], currency, "campaign", store_product_source=store_src)
        except money.BudgetError as exc:
            errors.append(f"campaign.budget: {exc}")

    # -- ad groups ---------------------------------------------------------
    names = set()
    for i, ag in enumerate(adgroups):
        where = f"adgroups[{i}]"
        name = ag.get("adgroup_name")
        if not _require(name, f"{where}.adgroup_name is required", errors):
            pass
        elif name in names:
            errors.append(f"{where}.adgroup_name {name!r} is duplicated in this spec")
        else:
            names.add(name)

        goal = ag.get("optimization_goal")
        if not _require(goal, f"{where}.optimization_goal is required", errors):
            pass
        elif goal in FILTER_ONLY_GOALS:
            errors.append(
                f"{where}.optimization_goal {goal!r} is a reporting filter, not a creatable goal. "
                "TikTok rejects it on /adgroup/create/."
            )
        elif goal in DEPRECATED_GOALS:
            errors.append(f"{where}.optimization_goal {goal!r} is {DEPRECATED_GOALS[goal]}")
        elif goal not in OPTIMIZATION_GOALS:
            errors.append(f"{where}.optimization_goal {goal!r} is not a known goal")

        if goal in GOALS_OWNING_EVENT and ag.get("optimization_event"):
            errors.append(
                f"{where}: optimization_goal {goal!r} sets optimization_event itself. "
                "Passing one is ignored or errors depending on the goal — remove it."
            )

        be = ag.get("billing_event")
        if not _require(be, f"{where}.billing_event is required by /adgroup/create/", errors):
            pass
        elif be not in BILLING_EVENTS:
            errors.append(f"{where}.billing_event {be!r} invalid")
        elif goal in GOAL_BILLING_EVENT and be != GOAL_BILLING_EVENT[goal]:
            errors.append(
                f"{where}: optimization_goal {goal!r} must be billed as "
                f"{GOAL_BILLING_EVENT[goal]!r}, not {be!r}. TikTok fixes this pairing — "
                "it is not a bidding choice."
            )

        pacing = ag.get("pacing")
        if pacing and pacing not in PACING_MODES:
            errors.append(
                f"{where}.pacing {pacing!r} invalid. Valid: "
                f"{', '.join(sorted(PACING_MODES))}."
            )
        elif not pacing and not cbo:
            errors.append(
                f"{where}.pacing is required when Campaign Budget Optimization is off. "
                "PACING_MODE_SMOOTH spreads the budget across the schedule; "
                "PACING_MODE_FAST spends it as fast as it can. Choose deliberately."
            )

        promo = ag.get("promotion_type")
        if promo and promo not in PROMOTION_TYPES:
            errors.append(f"{where}.promotion_type {promo!r} is not a known promotion type")
        elif not promo and objective and objective not in PROMOTION_TYPE_EXEMPT_OBJECTIVES:
            errors.append(
                f"{where}.promotion_type is required — TikTok only exempts objectives "
                f"{', '.join(sorted(PROMOTION_TYPE_EXEMPT_OBJECTIVES))}, and this campaign "
                f"is {objective!r}. It is the optimization location (WEBSITE, "
                "LEAD_GENERATION, APP_IOS, ...)."
            )

        _validate_attribution(ag, where, errors)

        bid = ag.get("bid_type")
        if bid and bid not in BID_TYPES:
            errors.append(
                f"{where}.bid_type {bid!r} invalid. TikTok has exactly two: "
                "BID_TYPE_NO_BID (Maximum Delivery) and BID_TYPE_CUSTOM (Cost Cap). "
                "Meta's bid-strategy vocabulary does not exist here."
            )
        # Cost Cap carries its bid in a DIFFERENT FIELD depending on the billing event.
        # bid_price is for CPC/CPM/CPV; conversion_bid_price is for OCPM. Demanding
        # bid_price on an OCPM conversion ad group is wrong, and stuffing it in sends a
        # field TikTok will not read as the bid.
        if bid == "BID_TYPE_CUSTOM":
            if be == "OCPM":
                if ag.get("conversion_bid_price") is None:
                    errors.append(
                        f"{where}.conversion_bid_price is required for Cost Cap on OCPM "
                        "(the target cost per conversion). bid_price is the wrong field here."
                    )
                if ag.get("bid_price") is not None:
                    errors.append(
                        f"{where}.bid_price must be omitted when billing_event is OCPM — "
                        "use conversion_bid_price."
                    )
            elif be in ("CPC", "CPM", "CPV"):
                if ag.get("bid_price") is None:
                    errors.append(
                        f"{where}.bid_price is required for Cost Cap on {be}."
                    )
                if ag.get("conversion_bid_price") is not None:
                    errors.append(
                        f"{where}.conversion_bid_price applies to OCPM only; "
                        f"billing_event is {be}."
                    )
        if bid == "BID_TYPE_NO_BID":
            for field in ("bid_price", "conversion_bid_price"):
                if ag.get(field) is not None:
                    errors.append(
                        f"{where}.{field} must be omitted when bid_type is BID_TYPE_NO_BID "
                        "(Maximum Delivery sets no bid)."
                    )

        pt = ag.get("placement_type")
        if not _require(pt, f"{where}.placement_type is required", errors):
            pass
        elif pt not in PLACEMENT_TYPES:
            errors.append(f"{where}.placement_type {pt!r} invalid")
        elif pt == "PLACEMENT_TYPE_NORMAL":
            pl = ag.get("placements") or []
            if not pl:
                errors.append(f"{where}.placements is required with PLACEMENT_TYPE_NORMAL")
            for p in pl:
                if p not in PLACEMENTS:
                    errors.append(f"{where}.placements has unknown/deprecated value {p!r}")
            if pl == ["PLACEMENT_GLOBAL_APP_BUNDLE"] and goal == "TRAFFIC_LANDING_PAGE_VIEW":
                errors.append(
                    f"{where}: Global App Bundle placement does not support the "
                    "TRAFFIC_LANDING_PAGE_VIEW optimization goal"
                )

        st = ag.get("schedule_type")
        if st and st not in SCHEDULE_TYPES:
            errors.append(f"{where}.schedule_type {st!r} invalid")
        if st == "SCHEDULE_START_END" and not (ag.get("schedule_start_time") and ag.get("schedule_end_time")):
            errors.append(f"{where}: SCHEDULE_START_END needs schedule_start_time and schedule_end_time")
        if not ag.get("schedule_start_time"):
            errors.append(
                f"{where}.schedule_start_time is required. Set it deliberately in the account's "
                f"timezone ({profile['timezone']}); a past start time does not error, it starts now."
            )

        if not cbo:
            ag_mode = ag.get("budget_mode")
            if not _require(ag_mode, f"{where}.budget_mode is required when CBO is off", errors):
                pass
            elif ag_mode not in BUDGET_MODES:
                errors.append(f"{where}.budget_mode {ag_mode!r} invalid")
            elif (c_mode, ag_mode) in INCOMPATIBLE:
                errors.append(
                    f"{where}: campaign BUDGET_MODE_DAY forbids an ad-group lifetime budget"
                )
            elif st == "SCHEDULE_FROM_NOW" and ag_mode == "BUDGET_MODE_TOTAL":
                errors.append(
                    f"{where}: continuous delivery (SCHEDULE_FROM_NOW) requires a daily or "
                    "dynamic-daily ad-group budget, not a lifetime budget"
                )
            if ag.get("budget") is None:
                errors.append(f"{where}.budget is required when CBO is off")
            elif spec_currency:
                ag_store = ag.get("product_source") in ("STORE", "SHOWCASE")
                try:
                    money.validate(ag["budget"], currency, "adgroup", store_product_source=ag_store)
                except money.BudgetError as exc:
                    errors.append(f"{where}.budget: {exc}")

        creatives = ag.get("creatives") or []
        if not creatives:
            errors.append(f"{where}.creatives must contain at least one ad")
        for j, cr in enumerate(creatives):
            cw = f"{where}.creatives[{j}]"
            _require(cr.get("ad_name"), f"{cw}.ad_name is required", errors)
            fmt = cr.get("ad_format")
            if not _require(fmt, f"{cw}.ad_format is required", errors):
                pass
            elif fmt not in AD_FORMATS:
                errors.append(
                    f"{cw}.ad_format {fmt!r} invalid. Note: CAROUSEL (TopBuzz) and image_mode "
                    "are deprecated; Collection Ads can no longer be created at all."
                )
            it = cr.get("identity_type")
            if not _require(it, f"{cw}.identity_type is required", errors):
                pass
            elif it not in IDENTITY_TYPES:
                errors.append(f"{cw}.identity_type {it!r} invalid")
            elif it != "CUSTOMIZED_USER" and not cr.get("identity_id"):
                errors.append(f"{cw}.identity_id is required for identity_type {it!r}")
            if fmt == "SINGLE_VIDEO" and not cr.get("video_id"):
                errors.append(f"{cw}.video_id is required for SINGLE_VIDEO")
            if fmt == "SINGLE_IMAGE" and not cr.get("image_ids"):
                errors.append(f"{cw}.image_ids is required for SINGLE_IMAGE")

    return errors


def _validate_attribution(ag, where, errors):
    """Attribution windows: co-required, enum-checked, and permanent once set.

    TikTok will silently apply account defaults if you pass nothing, which is how a
    strategy that specifies a 7-day click window ends up measured on whatever the
    account happened to be set to. Passing a partial set is rejected by TikTok.
    """
    click = ag.get("click_attribution_window")
    view = ag.get("view_attribution_window")
    engaged = ag.get("engaged_view_attribution_window")
    count = ag.get("attribution_event_count")

    for key, value, allowed in (
        ("click_attribution_window", click, CLICK_ATTRIBUTION_WINDOWS),
        ("view_attribution_window", view, VIEW_ATTRIBUTION_WINDOWS),
        ("engaged_view_attribution_window", engaged, ENGAGED_VIEW_ATTRIBUTION_WINDOWS),
        ("attribution_event_count", count, ATTRIBUTION_EVENT_COUNTS),
    ):
        if value is not None and value not in allowed:
            errors.append(f"{where}.{key} {value!r} invalid. Valid: {', '.join(sorted(allowed))}")

    if (click is None) != (view is None):
        errors.append(
            f"{where}: click_attribution_window and view_attribution_window must be passed "
            "together. TikTok rejects one without the other."
        )
    if engaged is not None and (click is None or view is None):
        errors.append(
            f"{where}: engaged_view_attribution_window requires both "
            "click_attribution_window and view_attribution_window."
        )


def normalize(spec, profile):
    """Validate, then produce the exact payloads that will be POSTed.

    Every object is forced to ``operation_status: DISABLE``. TikTok's default is
    ENABLE — omitting it creates a live, spending campaign. There is no spec
    field to override this; activation is a separate, confirmed command.
    """
    errors = validate(spec, profile)
    if errors:
        raise SpecError("Spec rejected:\n  - " + "\n  - ".join(errors))

    advertiser_id = profile["advertiser_id"]
    currency = profile["currency"]
    camp = spec["campaign"]
    cbo = bool(camp.get("budget_optimize_on"))

    campaign_payload = {
        "advertiser_id": advertiser_id,
        "campaign_name": camp["campaign_name"],
        "objective_type": camp["objective_type"],
        "special_industries": camp.get("special_industries") or [],
        "operation_status": "DISABLE",
    }
    for key in ("app_promotion_type", "virtual_objective_type", "sales_destination",
                "campaign_product_source", "campaign_type", "catalog_enabled",
                "is_search_campaign", "po_number", "app_id"):
        if camp.get(key) is not None:
            campaign_payload[key] = camp[key]
    if cbo:
        campaign_payload["budget_optimize_on"] = True
    if camp.get("budget_mode"):
        campaign_payload["budget_mode"] = camp["budget_mode"]
    if camp.get("budget") is not None:
        store_src = camp.get("campaign_product_source") == "STORE"
        campaign_payload["budget"] = float(
            money.validate(camp["budget"], currency, "campaign", store_product_source=store_src)
        )

    adgroup_payloads = []
    for ag in spec["adgroups"]:
        payload = {
            "advertiser_id": advertiser_id,
            "adgroup_name": ag["adgroup_name"],
            "optimization_goal": ag["optimization_goal"],
            "placement_type": ag["placement_type"],
            "schedule_type": ag.get("schedule_type", "SCHEDULE_FROM_NOW"),
            "schedule_start_time": ag["schedule_start_time"],
            "operation_status": "DISABLE",
        }
        passthrough = (
            "promotion_type", "promotion_target_type", "billing_event", "bid_type",
            "bid_price", "conversion_bid_price", "deep_bid_type", "roas_bid",
            "placements", "pixel_id", "optimization_event", "deep_cpa_bid",
            "schedule_end_time", "dayparting", "frequency", "frequency_schedule",
            "pacing", "app_id", "product_source", "product_set_id", "catalog_id",
            "store_id", "identity_id", "identity_type", "shopping_ads_type",
            "secondary_optimization_event", "skip_learning_phase",
            "audience_ids", "excluded_audience_ids", "targeting_expansion",
            # Attribution: permanent once set, and silently defaulted if omitted.
            "click_attribution_window", "view_attribution_window",
            "engaged_view_attribution_window", "attribution_event_count",
            # UK food advertising declarations — a compliance answer, not a setting.
            "is_hfss", "is_lhf_compliance",
            # Engagement surface. video_download_disabled CANNOT be changed after create.
            "comment_disabled", "video_download_disabled", "share_disabled",
        )
        for key in passthrough:
            if ag.get(key) is not None:
                payload[key] = ag[key]
        for key, value in (ag.get("targeting") or {}).items():
            payload[key] = value
        if not cbo:
            payload["budget_mode"] = ag["budget_mode"]
            ag_store = ag.get("product_source") in ("STORE", "SHOWCASE")
            payload["budget"] = float(
                money.validate(ag["budget"], currency, "adgroup", store_product_source=ag_store)
            )
        adgroup_payloads.append({"_name": ag["adgroup_name"], "payload": payload,
                                 "creatives": ag["creatives"]})

    return {
        "advertiser_id": advertiser_id,
        "currency": currency,
        "timezone": profile["timezone"],
        "cbo": cbo,
        "campaign": campaign_payload,
        "adgroups": adgroup_payloads,
    }


def ad_payload(advertiser_id, adgroup_id, creatives):
    """Build one /ad/create/ body. TikTok takes a list of creatives per call."""
    out = []
    for cr in creatives:
        item = {"ad_name": cr["ad_name"], "ad_format": cr["ad_format"],
                "identity_type": cr["identity_type"]}
        for key in ("identity_id", "identity_authorized_bc_id", "video_id", "image_ids",
                    "ad_text", "call_to_action", "call_to_action_id", "landing_page_url",
                    "display_name", "profile_image_url", "page_id", "tiktok_item_id",
                    "music_id", "deeplink", "deeplink_type", "impression_tracking_url",
                    "click_tracking_url", "utm_params", "product_specific_type",
                    "item_group_ids", "avatar_icon_web_uri", "creative_authorized",
                    # Symphony AIGC creative rewrites. Pass an explicit list to choose
                    # them; omit it to leave the ad as uploaded.
                    "creative_auto_enhancement_strategy_list"):
            if cr.get(key) is not None:
                item[key] = cr[key]
        out.append(item)
    return {
        "advertiser_id": advertiser_id,
        "adgroup_id": adgroup_id,
        "creatives": out,
        "operation_status": "DISABLE",
    }


def budget_summary(plan):
    """Operator-facing budget line. Major units, currency named, per object."""
    lines = []
    cur = plan["currency"]
    camp = plan["campaign"]
    if camp.get("budget") is not None:
        lines.append(f"campaign {camp['campaign_name']}: "
                     f"{money.describe(camp['budget'], cur)} ({camp.get('budget_mode')})"
                     + (" [CBO]" if plan["cbo"] else ""))
    for ag in plan["adgroups"]:
        p = ag["payload"]
        if p.get("budget") is not None:
            lines.append(f"  adgroup {p['adgroup_name']}: "
                         f"{money.describe(p['budget'], cur)} ({p.get('budget_mode')})")
        else:
            lines.append(f"  adgroup {p['adgroup_name']}: budget from campaign (CBO)")
    return lines


def total_daily(plan):
    """Sum of daily budgets actually in force, for the activation confirmation."""
    if plan["cbo"]:
        camp = plan["campaign"]
        if camp.get("budget_mode") in ("BUDGET_MODE_DAY", "BUDGET_MODE_DYNAMIC_DAILY_BUDGET"):
            return Decimal(str(camp.get("budget", 0)))
        return Decimal("0")
    total = Decimal("0")
    for ag in plan["adgroups"]:
        p = ag["payload"]
        if p.get("budget_mode") in ("BUDGET_MODE_DAY", "BUDGET_MODE_DYNAMIC_DAILY_BUDGET"):
            total += Decimal(str(p.get("budget", 0)))
    return total
