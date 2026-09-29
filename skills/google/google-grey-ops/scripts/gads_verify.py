"""Read every created object back through GAQL and diff it against the normalized spec.

A successful mutate proves the request was accepted, not that the account holds what you meant:
enum defaults fill silently and policy review runs after creation. Exit non-zero on any mismatch.
"""

from __future__ import annotations

from typing import Any

from gads_client import search

STRATEGY_TYPE = {
    "manual_cpc": "MANUAL_CPC",
    "maximize_conversions": "MAXIMIZE_CONVERSIONS",
    "maximize_conversion_value": "MAXIMIZE_CONVERSION_VALUE",
    "target_cpa": "TARGET_CPA",
    "target_roas": "TARGET_ROAS",
    "maximize_clicks": "TARGET_SPEND",
}


def _id(resource_name: str) -> str:
    return resource_name.rsplit("/", 1)[-1]


def verify(client: Any, customer_id: str, spec: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    camp = spec["campaign"]
    objects = state["objects"]
    campaign_rn = objects["campaign"]
    cid_ = _id(campaign_rn)
    problems: list[str] = []
    facts: dict[str, Any] = {}

    def check(name: str, expected: Any, actual: Any) -> None:
        facts[name] = actual
        if expected != actual:
            problems.append(f"{name}: expected {expected!r}, got {actual!r}")

    rows = search(client, customer_id, f"""
        SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type,
          campaign.bidding_strategy_type, campaign.tracking_url_template, campaign.final_url_suffix,
          campaign.network_settings.target_partner_search_network, campaign.network_settings.target_content_network,
          campaign.geo_target_type_setting.positive_geo_target_type,
          campaign.shopping_setting.merchant_id, campaign.shopping_setting.feed_label,
          campaign.shopping_setting.campaign_priority, campaign.contains_eu_political_advertising,
          campaign.asset_automation_settings, campaign.primary_status, campaign.primary_status_reasons,
          campaign.serving_status, campaign_budget.amount_micros, campaign_budget.explicitly_shared,
          campaign_budget.period
        FROM campaign WHERE campaign.id = {cid_}""")
    if not rows:
        return {"ok": False, "problems": [f"campaign {campaign_rn} not found"], "facts": {}}
    c = rows[0].campaign
    b = rows[0].campaign_budget
    check("campaign.name", camp["name"], c.name)
    check("campaign.status", "PAUSED", c.status.name)
    check("campaign.bidding_strategy_type", STRATEGY_TYPE[camp["bidding"]["strategy"]], c.bidding_strategy_type.name)
    check("budget.amount_micros", camp["daily_budget_micros"], b.amount_micros)
    check("budget.explicitly_shared", False, b.explicitly_shared)
    check("campaign.positive_geo_target_type", camp["positive_geo_target_type"],
          c.geo_target_type_setting.positive_geo_target_type.name)
    check("campaign.eu_political", "CONTAINS_EU_POLITICAL_ADVERTISING" if camp["eu_political_advertising"]
          else "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING", c.contains_eu_political_advertising.name)
    if camp.get("tracking_url_template"):
        check("campaign.tracking_url_template", camp["tracking_url_template"], c.tracking_url_template)
    if camp["kind"] == "search":
        check("campaign.search_partners", camp["search_partners"], c.network_settings.target_partner_search_network)
        check("campaign.content_network", camp["content_network"], c.network_settings.target_content_network)
    if camp["kind"] in ("pmax_retail", "shopping"):
        check("campaign.merchant_id", camp["merchant_id"], c.shopping_setting.merchant_id)
        if camp.get("feed_label"):
            check("campaign.feed_label", camp["feed_label"], c.shopping_setting.feed_label)
    if camp["kind"] == "shopping":
        check("campaign.campaign_priority", camp["campaign_priority"], c.shopping_setting.campaign_priority)
    if camp["kind"] == "pmax_retail":
        expansion = [s for s in c.asset_automation_settings
                     if s.asset_automation_type.name == "FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION"]
        status = expansion[0].asset_automation_status.name if expansion else "DEFAULT(OPTED_IN)"
        check("campaign.final_url_expansion", "OPTED_IN" if camp["final_url_expansion"] else "OPTED_OUT", status)
    facts["campaign.primary_status"] = c.primary_status.name
    facts["campaign.primary_status_reasons"] = [r.name for r in c.primary_status_reasons]
    facts["campaign.serving_status"] = c.serving_status.name

    crit = search(client, customer_id, f"""
        SELECT campaign_criterion.type, campaign_criterion.negative,
          campaign_criterion.location.geo_target_constant, campaign_criterion.language.language_constant,
          campaign_criterion.keyword.text, campaign_criterion.brand_list.shared_set
        FROM campaign_criterion WHERE campaign.id = {cid_} AND campaign_criterion.status != 'REMOVED'""")
    locs = sorted(_id(r.campaign_criterion.location.geo_target_constant) for r in crit
                  if r.campaign_criterion.type_.name == "LOCATION")
    langs = sorted(_id(r.campaign_criterion.language.language_constant) for r in crit
                   if r.campaign_criterion.type_.name == "LANGUAGE")
    check("campaign.locations", sorted(camp["locations"]), locs)
    check("campaign.languages", sorted(camp["languages"]), langs)
    negs = sorted(r.campaign_criterion.keyword.text for r in crit
                  if r.campaign_criterion.type_.name == "KEYWORD" and r.campaign_criterion.negative)
    check("campaign.negative_keywords", sorted(n["text"] for n in camp["negative_keywords"]), negs)
    if camp.get("brand_exclusion_shared_set_id"):
        brands = [_id(r.campaign_criterion.brand_list.shared_set) for r in crit
                  if r.campaign_criterion.type_.name == "BRAND_LIST"]
        check("campaign.brand_exclusion", [str(camp["brand_exclusion_shared_set_id"])], brands)

    if camp["kind"] in ("search", "shopping"):
        ags = search(client, customer_id, f"""
            SELECT ad_group.id, ad_group.name, ad_group.status, ad_group.type, ad_group.cpc_bid_micros
            FROM ad_group WHERE campaign.id = {cid_} AND ad_group.status != 'REMOVED'""")
        by_name = {r.ad_group.name: r.ad_group for r in ags}
        check("ad_groups", sorted(a["name"] for a in spec["ad_groups"]), sorted(by_name))
        expected_type = "SEARCH_STANDARD" if camp["kind"] == "search" else "SHOPPING_PRODUCT_ADS"
        for ag_spec in spec["ad_groups"]:
            ag = by_name.get(ag_spec["name"])
            if ag is None:
                continue
            check(f"ad_group[{ag_spec['name']}].status", "PAUSED", ag.status.name)
            check(f"ad_group[{ag_spec['name']}].type", expected_type, ag.type_.name)
            if ag_spec.get("cpc_bid_micros"):
                check(f"ad_group[{ag_spec['name']}].cpc_bid_micros", ag_spec["cpc_bid_micros"], ag.cpc_bid_micros)
        ads = search(client, customer_id, f"""
            SELECT ad_group.name, ad_group_ad.status, ad_group_ad.policy_summary.approval_status,
              ad_group_ad.policy_summary.review_status, ad_group_ad.ad.final_urls,
              ad_group_ad.ad.responsive_search_ad.headlines, ad_group_ad.ad.responsive_search_ad.descriptions,
              ad_group_ad.ad.responsive_search_ad.path1, ad_group_ad.ad.responsive_search_ad.path2,
              ad_group_ad.ad.type
            FROM ad_group_ad WHERE campaign.id = {cid_} AND ad_group_ad.status != 'REMOVED'""")
        facts["ads"] = []
        for r in ads:
            facts["ads"].append({
                "ad_group": r.ad_group.name, "status": r.ad_group_ad.status.name, "type": r.ad_group_ad.ad.type_.name,
                "approval": r.ad_group_ad.policy_summary.approval_status.name,
                "review": r.ad_group_ad.policy_summary.review_status.name,
                "final_urls": list(r.ad_group_ad.ad.final_urls),
                "headlines": [h.text for h in r.ad_group_ad.ad.responsive_search_ad.headlines],
                "pins": {h.text: h.pinned_field.name for h in r.ad_group_ad.ad.responsive_search_ad.headlines
                         if h.pinned_field.name not in ("UNSPECIFIED", "UNKNOWN")},
                "descriptions": [d.text for d in r.ad_group_ad.ad.responsive_search_ad.descriptions],
                "path1": r.ad_group_ad.ad.responsive_search_ad.path1 or None,
                "path2": r.ad_group_ad.ad.responsive_search_ad.path2 or None,
            })
            if r.ad_group_ad.status.name != "PAUSED":
                problems.append(f"ad in {r.ad_group.name} is {r.ad_group_ad.status.name}, expected PAUSED")
            if r.ad_group_ad.policy_summary.approval_status.name == "DISAPPROVED":
                problems.append(f"ad in {r.ad_group.name} DISAPPROVED — build a new ad, do not enable")
        expected_ads = sum(len(a.get("ads", [])) or 1 for a in spec["ad_groups"])
        check("ads.count", expected_ads, len(ads))
        if camp["kind"] == "search":
            for ag_spec in spec["ad_groups"]:
                for ad_spec in ag_spec["ads"]:
                    match = [a for a in facts["ads"] if a["ad_group"] == ag_spec["name"]
                             and sorted(a["headlines"]) == sorted(ad_spec["headlines"])
                             and sorted(a["descriptions"]) == sorted(ad_spec["descriptions"])
                             and sorted(a["final_urls"]) == sorted(ad_spec["final_urls"])]
                    if not match:
                        problems.append(f"RSA in {ag_spec['name']} differs from spec (headlines/descriptions/final_urls)")
                        continue
                    got = match[0]
                    want_pins = {}
                    for key, field in ad_spec["pins"].items():
                        text = ad_spec["headlines"][int(key)] if str(key).isdigit() else key
                        want_pins[text] = field
                    check(f"rsa[{ag_spec['name']}].pins", want_pins, got["pins"])
                    check(f"rsa[{ag_spec['name']}].path1", ad_spec.get("path1"), got["path1"])
                    check(f"rsa[{ag_spec['name']}].path2", ad_spec.get("path2"), got["path2"])
            kws = search(client, customer_id, f"""
                SELECT ad_group.name, ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
                  ad_group_criterion.status, ad_group_criterion.negative
                FROM ad_group_criterion WHERE campaign.id = {cid_} AND ad_group_criterion.type = 'KEYWORD'
                  AND ad_group_criterion.status != 'REMOVED'""")
            got = sorted((r.ad_group.name, r.ad_group_criterion.keyword.text,
                          r.ad_group_criterion.keyword.match_type.name) for r in kws
                         if not r.ad_group_criterion.negative)
            want = sorted((a["name"], k["text"], k["match_type"]) for a in spec["ad_groups"] for k in a["keywords"])
            check("keywords", want, got)
        else:
            parts = search(client, customer_id, f"""
                SELECT ad_group.name, ad_group_criterion.listing_group.type,
                  ad_group_criterion.listing_group.case_value.product_brand.value,
                  ad_group_criterion.listing_group.case_value.product_custom_attribute.value,
                  ad_group_criterion.listing_group.case_value.product_item_id.value,
                  ad_group_criterion.cpc_bid_micros, ad_group_criterion.negative
                FROM ad_group_criterion WHERE campaign.id = {cid_} AND ad_group_criterion.type = 'LISTING_GROUP'
                  AND ad_group_criterion.status != 'REMOVED'""")
            facts["listing_groups"] = [{
                "ad_group": r.ad_group.name, "type": r.ad_group_criterion.listing_group.type_.name,
                "brand": r.ad_group_criterion.listing_group.case_value.product_brand.value,
                "custom": r.ad_group_criterion.listing_group.case_value.product_custom_attribute.value,
                "item_id": r.ad_group_criterion.listing_group.case_value.product_item_id.value,
                "cpc_bid_micros": r.ad_group_criterion.cpc_bid_micros, "negative": r.ad_group_criterion.negative,
            } for r in parts]
            for ag_spec in spec["ad_groups"]:
                lg = ag_spec["listing_groups"]
                want_units = 1 if lg["dimension"] is None else len(lg["units"]) + 2
                got_units = len([p for p in facts["listing_groups"] if p["ad_group"] == ag_spec["name"]])
                check(f"ad_group[{ag_spec['name']}].partition_nodes", want_units, got_units)

    if camp["kind"] == "pmax_retail":
        groups = search(client, customer_id, f"""
            SELECT asset_group.id, asset_group.name, asset_group.status, asset_group.final_urls,
              asset_group.primary_status, asset_group.primary_status_reasons, asset_group.ad_strength
            FROM asset_group WHERE campaign.id = {cid_} AND asset_group.status != 'REMOVED'""")
        by_name = {r.asset_group.name: r.asset_group for r in groups}
        check("asset_groups", sorted(a["name"] for a in spec["asset_groups"]), sorted(by_name))
        for ag in by_name.values():
            check(f"asset_group[{ag.name}].status", "PAUSED", ag.status.name)
            facts[f"asset_group[{ag.name}].primary_status"] = ag.primary_status.name
            facts[f"asset_group[{ag.name}].ad_strength"] = ag.ad_strength.name
        links = search(client, customer_id, f"""
            SELECT asset_group.name, asset_group_asset.field_type, asset_group_asset.status,
              asset_group_asset.policy_summary.approval_status, asset.text_asset.text, asset.type
            FROM asset_group_asset WHERE campaign.id = {cid_} AND asset_group_asset.status != 'REMOVED'""")
        per_group: dict[str, dict[str, int]] = {}
        for r in links:
            per_group.setdefault(r.asset_group.name, {})
            per_group[r.asset_group.name][r.asset_group_asset.field_type.name] = \
                per_group[r.asset_group.name].get(r.asset_group_asset.field_type.name, 0) + 1
            if r.asset_group_asset.policy_summary.approval_status.name == "DISAPPROVED":
                problems.append(f"asset DISAPPROVED in {r.asset_group.name}: {r.asset.text_asset.text!r}")
        facts["asset_group_assets"] = per_group
        for ag_spec in spec["asset_groups"]:
            counts = per_group.get(ag_spec["name"], {})
            check(f"asset_group[{ag_spec['name']}].HEADLINE", len(ag_spec["headlines"]), counts.get("HEADLINE", 0))
            check(f"asset_group[{ag_spec['name']}].DESCRIPTION", len(ag_spec["descriptions"]),
                  counts.get("DESCRIPTION", 0))
            check(f"asset_group[{ag_spec['name']}].LOGO>=1", True, counts.get("LOGO", 0) >= 1)
            check(f"asset_group[{ag_spec['name']}].MARKETING_IMAGE>=1", True, counts.get("MARKETING_IMAGE", 0) >= 1)
        filters = search(client, customer_id, f"""
            SELECT asset_group.name, asset_group_listing_group_filter.type,
              asset_group_listing_group_filter.case_value.product_custom_attribute.value,
              asset_group_listing_group_filter.case_value.product_brand.value,
              asset_group_listing_group_filter.parent_listing_group_filter
            FROM asset_group_listing_group_filter WHERE campaign.id = {cid_}""")
        facts["listing_filters"] = [{"asset_group": r.asset_group.name,
                                     "type": r.asset_group_listing_group_filter.type_.name,
                                     "custom": r.asset_group_listing_group_filter.case_value.product_custom_attribute.value,
                                     "brand": r.asset_group_listing_group_filter.case_value.product_brand.value}
                                    for r in filters]
        for ag_spec in spec["asset_groups"]:
            lf = ag_spec["listing_filter"]
            want = 1 if lf is None else len(lf["units"]) + 2
            got = len([f for f in facts["listing_filters"] if f["asset_group"] == ag_spec["name"]])
            check(f"asset_group[{ag_spec['name']}].listing_filter_nodes", want, got)
        signals = search(client, customer_id, f"""
            SELECT asset_group.name, asset_group_signal.search_theme.text, asset_group_signal.audience.audience,
              asset_group_signal.approval_status
            FROM asset_group_signal WHERE campaign.id = {cid_}""")
        got_themes = sorted(r.asset_group_signal.search_theme.text for r in signals
                            if r.asset_group_signal.search_theme.text)
        check("search_themes", sorted(t for a in spec["asset_groups"] for t in a["search_themes"]), got_themes)

    return {"ok": not problems, "problems": problems, "facts": facts}
