"""Normalized spec -> MutateOperation graph. Every object is created PAUSED.

Defaults enforced here (override only via spec fields that exist):
  status PAUSED on campaign / ad group / ad / asset group
  Search Partners off, Display expansion off (spec.network flips them on explicitly)
  positive geo target type PRESENCE (Google's default is PRESENCE_OR_INTEREST)
  EU political advertising declared (required field)
  PMax: non-shared budget, final URL expansion opted OUT unless spec says true,
        listing group root UNIT_INCLUDED or a SUBDIVISION tree over one dimension
  Shopping: ad group type SHOPPING_PRODUCT_ADS, partition root SUBDIVISION with explicit "others" leaf
"""

from __future__ import annotations

import base64
import pathlib
from typing import Any

import gads_client

TMP = {"budget": -1, "campaign": -2}
CUSTOM_LABEL_INDEX = {f"custom_label_{i}": f"INDEX{i}" for i in range(5)}


class BuildError(Exception):
    pass


class Graph:
    """Collects operations with unique negative temp ids and remembers what each id means."""

    def __init__(self, client: Any, customer_id: str):
        self.client = client
        self.cid = customer_id
        self.ops: list[Any] = []
        self.next_tmp = -1
        self.labels: dict[str, str] = {}  # resource_name (temp) -> human label

    def tmp(self) -> int:
        value = self.next_tmp
        self.next_tmp -= 1
        return value

    def path(self, service: str, method: str, tmp_id: int) -> str:
        return getattr(self.client.get_service(service), method)(self.cid, str(tmp_id))

    def child_path(self, service: str, method: str, parent_rn: str, tmp_id: int) -> str:
        """Composite child resource (ad group criterion, listing group filter): parent id ~ own temp id."""
        parent_id = parent_rn.rsplit("/", 1)[-1]
        return getattr(self.client.get_service(service), method)(self.cid, parent_id, str(tmp_id))

    def op(self, field: str):
        operation = self.client.get_type("MutateOperation")
        target = getattr(operation, field).create
        self.ops.append(operation)
        return target

    def enum(self, name: str, value: str):
        return getattr(getattr(self.client.enums, name), value)


def _budget(g: Graph, spec: dict[str, Any], shared_ok: bool) -> str:
    rn = g.path("CampaignBudgetService", "campaign_budget_path", g.tmp())
    b = g.op("campaign_budget_operation")
    b.resource_name = rn
    b.name = f"{spec['campaign']['name']} budget"
    b.amount_micros = spec["campaign"]["daily_budget_micros"]
    b.delivery_method = g.enum("BudgetDeliveryMethodEnum", "STANDARD")
    b.explicitly_shared = False
    b.period = g.enum("BudgetPeriodEnum", "DAILY")
    g.labels[rn] = "campaign_budget"
    return rn


def _bidding(g: Graph, c: Any, bid: dict[str, Any]) -> None:
    s = bid["strategy"]
    if s == "manual_cpc":
        c.manual_cpc.enhanced_cpc_enabled = bid.get("enhanced_cpc", False)
    elif s == "maximize_conversions":
        if "target_cpa_micros" in bid:
            c.maximize_conversions.target_cpa_micros = bid["target_cpa_micros"]
        else:
            g.client.copy_from(c.maximize_conversions, g.client.get_type("MaximizeConversions"))
    elif s == "maximize_conversion_value":
        if "target_roas" in bid:
            c.maximize_conversion_value.target_roas = bid["target_roas"]
        else:
            g.client.copy_from(c.maximize_conversion_value, g.client.get_type("MaximizeConversionValue"))
    elif s == "target_cpa":
        c.target_cpa.target_cpa_micros = bid["target_cpa_micros"]
    elif s == "target_roas":
        c.target_roas.target_roas = bid["target_roas"]
    elif s == "maximize_clicks":
        g.client.copy_from(c.target_spend, g.client.get_type("TargetSpend"))
        if "cpc_bid_ceiling_micros" in bid:
            c.target_spend.cpc_bid_ceiling_micros = bid["cpc_bid_ceiling_micros"]
    else:
        raise BuildError(f"unknown bidding strategy {s}")


def _campaign(g: Graph, spec: dict[str, Any], budget_rn: str) -> str:
    camp = spec["campaign"]
    rn = g.path("CampaignService", "campaign_path", g.tmp())
    c = g.op("campaign_operation")
    c.resource_name = rn
    c.name = camp["name"]
    c.status = g.enum("CampaignStatusEnum", "PAUSED")
    c.campaign_budget = budget_rn
    kind = camp["kind"]
    c.advertising_channel_type = g.enum("AdvertisingChannelTypeEnum", {
        "search": "SEARCH", "pmax_retail": "PERFORMANCE_MAX", "shopping": "SHOPPING"}[kind])
    c.contains_eu_political_advertising = g.enum(
        "EuPoliticalAdvertisingStatusEnum",
        "CONTAINS_EU_POLITICAL_ADVERTISING" if camp["eu_political_advertising"]
        else "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING")
    c.geo_target_type_setting.positive_geo_target_type = g.enum(
        "PositiveGeoTargetTypeEnum", camp["positive_geo_target_type"])
    c.geo_target_type_setting.negative_geo_target_type = g.enum("NegativeGeoTargetTypeEnum", "PRESENCE")
    if camp.get("tracking_url_template"):
        c.tracking_url_template = camp["tracking_url_template"]
    if camp.get("final_url_suffix"):
        c.final_url_suffix = camp["final_url_suffix"]
    if camp.get("start_date"):
        c.start_date = camp["start_date"]
    _bidding(g, c, camp["bidding"])
    if kind == "search":
        c.network_settings.target_google_search = True
        c.network_settings.target_search_network = True
        c.network_settings.target_partner_search_network = camp["search_partners"]
        c.network_settings.target_content_network = camp["content_network"]
    if kind in ("pmax_retail", "shopping"):
        c.shopping_setting.merchant_id = camp["merchant_id"]
        if camp.get("feed_label"):
            c.shopping_setting.feed_label = camp["feed_label"]
    if kind == "shopping":
        c.shopping_setting.campaign_priority = camp["campaign_priority"]
        c.shopping_setting.enable_local = camp["enable_local"]
    if kind == "pmax_retail":
        c.brand_guidelines_enabled = False  # new PMax defaults to brand guidelines = campaign-level logo/name; we link them per asset group
        setting = type(c).AssetAutomationSetting()
        setting.asset_automation_type = g.enum("AssetAutomationTypeEnum",
                                               "FINAL_URL_EXPANSION_TEXT_ASSET_AUTOMATION")
        setting.asset_automation_status = g.enum(
            "AssetAutomationStatusEnum", "OPTED_IN" if camp["final_url_expansion"] else "OPTED_OUT")
        c.asset_automation_settings.append(setting)
    g.labels[rn] = "campaign"
    return rn


def _criteria(g: Graph, spec: dict[str, Any], campaign_rn: str) -> None:
    camp = spec["campaign"]
    for loc in camp["locations"]:
        cc = g.op("campaign_criterion_operation")
        cc.campaign = campaign_rn
        cc.location.geo_target_constant = f"geoTargetConstants/{loc}"
    for lang in camp["languages"]:
        cc = g.op("campaign_criterion_operation")
        cc.campaign = campaign_rn
        cc.language.language_constant = f"languageConstants/{lang}"
    for neg in camp["negative_keywords"]:
        cc = g.op("campaign_criterion_operation")
        cc.campaign = campaign_rn
        cc.negative = True
        cc.keyword.text = neg["text"]
        cc.keyword.match_type = g.enum("KeywordMatchTypeEnum", neg["match_type"])
    if camp.get("brand_exclusion_shared_set_id"):
        cc = g.op("campaign_criterion_operation")
        cc.campaign = campaign_rn
        cc.negative = True
        cc.brand_list.shared_set = g.client.get_service("SharedSetService").shared_set_path(
            g.cid, str(camp["brand_exclusion_shared_set_id"]))


def _search_ad_groups(g: Graph, spec: dict[str, Any], campaign_rn: str) -> None:
    for ag_spec in spec["ad_groups"]:
        ag_rn = g.path("AdGroupService", "ad_group_path", g.tmp())
        ag = g.op("ad_group_operation")
        ag.resource_name = ag_rn
        ag.name = ag_spec["name"]
        ag.campaign = campaign_rn
        ag.status = g.enum("AdGroupStatusEnum", "PAUSED")
        ag.type_ = g.enum("AdGroupTypeEnum", "SEARCH_STANDARD")
        if ag_spec.get("cpc_bid_micros"):
            ag.cpc_bid_micros = ag_spec["cpc_bid_micros"]
        g.labels[ag_rn] = f"ad_group:{ag_spec['name']}"
        for kw in ag_spec["keywords"]:
            crit = g.op("ad_group_criterion_operation")
            crit.ad_group = ag_rn
            crit.status = g.enum("AdGroupCriterionStatusEnum", "ENABLED")
            crit.keyword.text = kw["text"]
            crit.keyword.match_type = g.enum("KeywordMatchTypeEnum", kw["match_type"])
            if kw.get("cpc_bid_micros"):
                crit.cpc_bid_micros = kw["cpc_bid_micros"]
        for ad_spec in ag_spec["ads"]:
            ad = g.op("ad_group_ad_operation")
            ad.ad_group = ag_rn
            ad.status = g.enum("AdGroupAdStatusEnum", "PAUSED")
            ad.ad.final_urls.extend(ad_spec["final_urls"])
            for i, text in enumerate(ad_spec["headlines"]):
                asset = g.client.get_type("AdTextAsset")
                asset.text = text
                pin = ad_spec["pins"].get(str(i)) or ad_spec["pins"].get(text)
                if pin:
                    asset.pinned_field = g.enum("ServedAssetFieldTypeEnum", pin)
                ad.ad.responsive_search_ad.headlines.append(asset)
            for text in ad_spec["descriptions"]:
                asset = g.client.get_type("AdTextAsset")
                asset.text = text
                ad.ad.responsive_search_ad.descriptions.append(asset)
            if ad_spec.get("path1"):
                ad.ad.responsive_search_ad.path1 = ad_spec["path1"]
            if ad_spec.get("path2"):
                ad.ad.responsive_search_ad.path2 = ad_spec["path2"]
        for sl in ag_spec.get("sitelinks", []):
            asset_rn = g.path("AssetService", "asset_path", g.tmp())
            a = g.op("asset_operation")
            a.resource_name = asset_rn
            a.final_urls.extend(sl["final_urls"])
            a.sitelink_asset.link_text = sl["link_text"]
            if sl.get("description1"):
                a.sitelink_asset.description1 = sl["description1"]
            if sl.get("description2"):
                a.sitelink_asset.description2 = sl["description2"]
            link = g.op("ad_group_asset_operation")
            link.ad_group = ag_rn
            link.asset = asset_rn
            link.field_type = g.enum("AssetFieldTypeEnum", "SITELINK")


def _dimension(g: Graph, target: Any, dimension: str, value: str | None, for_pmax: bool) -> None:
    """Set one listing dimension on ListingDimensionInfo (shopping) or ListingGroupFilterDimension (pmax)."""
    if dimension.startswith("custom_label"):
        attr = target.product_custom_attribute
        attr.index = g.enum("ListingGroupFilterCustomAttributeIndexEnum" if for_pmax
                            else "ProductCustomAttributeIndexEnum", CUSTOM_LABEL_INDEX[dimension])
        if value is not None:
            attr.value = value
    elif dimension == "brand":
        if value is not None:
            target.product_brand.value = value
        else:
            g.client.copy_from(target.product_brand, type(target.product_brand)())
    elif dimension == "item_id":
        if value is not None:
            target.product_item_id.value = value
        else:
            g.client.copy_from(target.product_item_id, type(target.product_item_id)())
    elif dimension == "product_type":
        target.product_type.level = g.enum("ListingGroupFilterProductTypeLevelEnum" if for_pmax
                                           else "ProductTypeLevelEnum", "LEVEL1")
        if value is not None:
            target.product_type.value = value
    elif dimension == "category":
        target.product_category.level = g.enum("ListingGroupFilterProductCategoryLevelEnum" if for_pmax
                                               else "ProductCategoryLevelEnum", "LEVEL1")
        if value is not None:
            target.product_category.category_id = int(value)
    elif dimension == "condition":
        if value is not None:
            target.product_condition.condition = g.enum(
                "ListingGroupFilterProductConditionEnum" if for_pmax else "ProductConditionEnum", value.upper())
        else:
            g.client.copy_from(target.product_condition, type(target.product_condition)())
    elif dimension == "channel":
        if value is not None:
            target.product_channel.channel = g.enum(
                "ListingGroupFilterProductChannelEnum" if for_pmax else "ProductChannelEnum", value.upper())
        else:
            g.client.copy_from(target.product_channel, type(target.product_channel)())
    else:
        raise BuildError(f"unsupported listing dimension {dimension}")


def _shopping_ad_groups(g: Graph, spec: dict[str, Any], campaign_rn: str) -> None:
    for ag_spec in spec["ad_groups"]:
        ag_rn = g.path("AdGroupService", "ad_group_path", g.tmp())
        ag = g.op("ad_group_operation")
        ag.resource_name = ag_rn
        ag.name = ag_spec["name"]
        ag.campaign = campaign_rn
        ag.status = g.enum("AdGroupStatusEnum", "PAUSED")
        ag.type_ = g.enum("AdGroupTypeEnum", "SHOPPING_PRODUCT_ADS")
        if ag_spec.get("cpc_bid_micros"):
            ag.cpc_bid_micros = ag_spec["cpc_bid_micros"]
        g.labels[ag_rn] = f"ad_group:{ag_spec['name']}"
        ad = g.op("ad_group_ad_operation")
        ad.ad_group = ag_rn
        ad.status = g.enum("AdGroupAdStatusEnum", "PAUSED")
        g.client.copy_from(ad.ad.shopping_product_ad, g.client.get_type("ShoppingProductAdInfo"))
        lg = ag_spec["listing_groups"]
        root_rn = g.child_path("AdGroupCriterionService", "ad_group_criterion_path", ag_rn, g.tmp())
        root = g.op("ad_group_criterion_operation")
        root.resource_name = root_rn
        root.ad_group = ag_rn
        root.status = g.enum("AdGroupCriterionStatusEnum", "ENABLED")
        if lg["dimension"] is None:
            root.listing_group.type_ = g.enum("ListingGroupTypeEnum", "UNIT")
            root.cpc_bid_micros = lg["others"]["cpc_bid_micros"]
            continue
        root.listing_group.type_ = g.enum("ListingGroupTypeEnum", "SUBDIVISION")
        for unit in lg["units"]:
            leaf = g.op("ad_group_criterion_operation")
            leaf.ad_group = ag_rn
            leaf.status = g.enum("AdGroupCriterionStatusEnum", "ENABLED")
            leaf.listing_group.type_ = g.enum("ListingGroupTypeEnum", "UNIT")
            leaf.listing_group.parent_ad_group_criterion = root_rn
            _dimension(g, leaf.listing_group.case_value, lg["dimension"], unit["value"], for_pmax=False)
            if unit.get("exclude"):
                leaf.negative = True
            else:
                leaf.cpc_bid_micros = unit["cpc_bid_micros"]
        others = g.op("ad_group_criterion_operation")
        others.ad_group = ag_rn
        others.status = g.enum("AdGroupCriterionStatusEnum", "ENABLED")
        others.listing_group.type_ = g.enum("ListingGroupTypeEnum", "UNIT")
        others.listing_group.parent_ad_group_criterion = root_rn
        _dimension(g, others.listing_group.case_value, lg["dimension"], None, for_pmax=False)
        if lg["others"] == "exclude":
            others.negative = True
        else:
            others.cpc_bid_micros = lg["others"]["cpc_bid_micros"]


def image_bytes(ref: str) -> bytes | None:
    """Local file path -> bytes; anything else is treated as an existing asset id."""
    p = pathlib.Path(ref).expanduser()
    if p.is_file():
        return p.read_bytes()
    return None


def pmax_asset_operations(g: Graph, spec: dict[str, Any]) -> tuple[list[Any], dict[str, list[tuple[str, str]]]]:
    """Phase 1 for PMax: text + image assets. Returns ops and a map of asset_group name ->
    [(placeholder_key, field_type)], resolved to real resource names after the create returns."""
    mapping: dict[str, list[tuple[str, str]]] = {}
    ops: list[Any] = []
    for ag in spec["asset_groups"]:
        pairs: list[tuple[str, str]] = []

        def text(value: str, field: str) -> None:
            op = g.client.get_type("MutateOperation")
            a = op.asset_operation.create
            a.text_asset.text = value
            ops.append(op)
            pairs.append((f"text:{value}", field))

        for h in ag["headlines"]:
            text(h, "HEADLINE")
        for h in ag["long_headlines"]:
            text(h, "LONG_HEADLINE")
        for d in ag["descriptions"]:
            text(d, "DESCRIPTION")
        text(ag["business_name"], "BUSINESS_NAME")
        for slot, field in (("marketing", "MARKETING_IMAGE"), ("square", "SQUARE_MARKETING_IMAGE"),
                            ("logo", "LOGO"), ("portrait", "PORTRAIT_MARKETING_IMAGE")):
            for ref in ag["images"].get(slot, []):
                data = image_bytes(ref)
                if data is None:
                    pairs.append((f"asset:{ref}", field))
                    continue
                op = g.client.get_type("MutateOperation")
                a = op.asset_operation.create
                a.name = f"{ag['name']} {slot} {pathlib.Path(ref).name}"[:128]
                a.image_asset.data = data
                a.type_ = g.enum("AssetTypeEnum", "IMAGE")
                ops.append(op)
                pairs.append((f"file:{ref}", field))
        mapping[ag["name"]] = pairs
    return ops, mapping


def image_b64(ref: str) -> str | None:
    data = image_bytes(ref)
    return base64.b64encode(data).decode() if data else None


def _pmax_asset_groups(g: Graph, spec: dict[str, Any], campaign_rn: str,
                       assets: dict[str, dict[str, str]]) -> None:
    """assets: asset_group name -> {placeholder_key: resource_name}."""
    for ag_spec in spec["asset_groups"]:
        ag_rn = g.path("AssetGroupService", "asset_group_path", g.tmp())
        ag = g.op("asset_group_operation")
        ag.resource_name = ag_rn
        ag.name = ag_spec["name"]
        ag.campaign = campaign_rn
        ag.status = g.enum("AssetGroupStatusEnum", "PAUSED")
        ag.final_urls.extend(ag_spec["final_urls"])
        ag.final_mobile_urls.extend(ag_spec["final_urls"])
        g.labels[ag_rn] = f"asset_group:{ag_spec['name']}"
        for key, field in _asset_pairs(ag_spec):
            rn = assets.get(ag_spec["name"], {}).get(key)
            if rn is None:
                raise BuildError(f"asset {key} for {ag_spec['name']} was not created")
            link = g.op("asset_group_asset_operation")
            link.asset_group = ag_rn
            link.asset = rn
            link.field_type = g.enum("AssetFieldTypeEnum", field)
        for theme in ag_spec["search_themes"]:
            s = g.op("asset_group_signal_operation")
            s.asset_group = ag_rn
            s.search_theme.text = theme
        for aud in ag_spec["audience_ids"]:
            s = g.op("asset_group_signal_operation")
            s.asset_group = ag_rn
            s.audience.audience = f"customers/{g.cid}/audiences/{aud}"
        lf = ag_spec["listing_filter"]
        root_rn = g.child_path("AssetGroupListingGroupFilterService",
                               "asset_group_listing_group_filter_path", ag_rn, g.tmp())
        root = g.op("asset_group_listing_group_filter_operation")
        root.resource_name = root_rn
        root.asset_group = ag_rn
        root.listing_source = g.enum("ListingGroupFilterListingSourceEnum", "SHOPPING")
        if lf is None:
            root.type_ = g.enum("ListingGroupFilterTypeEnum", "UNIT_INCLUDED")
            continue
        root.type_ = g.enum("ListingGroupFilterTypeEnum", "SUBDIVISION")
        for unit in lf["units"]:
            leaf = g.op("asset_group_listing_group_filter_operation")
            leaf.asset_group = ag_rn
            leaf.listing_source = g.enum("ListingGroupFilterListingSourceEnum", "SHOPPING")
            leaf.type_ = g.enum("ListingGroupFilterTypeEnum", "UNIT_INCLUDED")
            leaf.parent_listing_group_filter = root_rn
            _dimension(g, leaf.case_value, lf["dimension"], unit["value"], for_pmax=True)
        others = g.op("asset_group_listing_group_filter_operation")
        others.asset_group = ag_rn
        others.listing_source = g.enum("ListingGroupFilterListingSourceEnum", "SHOPPING")
        others.type_ = g.enum("ListingGroupFilterTypeEnum", "UNIT_EXCLUDED")
        others.parent_listing_group_filter = root_rn
        _dimension(g, others.case_value, lf["dimension"], None, for_pmax=True)


def _asset_pairs(ag: dict[str, Any]) -> list[tuple[str, str]]:
    pairs = [(f"text:{h}", "HEADLINE") for h in ag["headlines"]]
    pairs += [(f"text:{h}", "LONG_HEADLINE") for h in ag["long_headlines"]]
    pairs += [(f"text:{d}", "DESCRIPTION") for d in ag["descriptions"]]
    pairs.append((f"text:{ag['business_name']}", "BUSINESS_NAME"))
    for slot, field in (("marketing", "MARKETING_IMAGE"), ("square", "SQUARE_MARKETING_IMAGE"),
                        ("logo", "LOGO"), ("portrait", "PORTRAIT_MARKETING_IMAGE")):
        for ref in ag["images"].get(slot, []):
            key = f"file:{ref}" if image_bytes(ref) is not None else f"asset:{ref}"
            pairs.append((key, field))
    return pairs


def resolve_existing_assets(g: Graph, spec: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Placeholders that point at existing asset ids need no creation."""
    out: dict[str, dict[str, str]] = {}
    for ag in spec["asset_groups"]:
        for key, _ in _asset_pairs(ag):
            if key.startswith("asset:"):
                out.setdefault(ag["name"], {})[key] = g.client.get_service("AssetService").asset_path(
                    g.cid, key.split(":", 1)[1])
    return out


def build_graph(client: Any, customer_id: str, spec: dict[str, Any],
                pmax_assets: dict[str, dict[str, str]] | None = None) -> Graph:
    g = Graph(client, customer_id)
    budget_rn = _budget(g, spec, shared_ok=False)
    campaign_rn = _campaign(g, spec, budget_rn)
    _criteria(g, spec, campaign_rn)
    kind = spec["campaign"]["kind"]
    if kind == "search":
        _search_ad_groups(g, spec, campaign_rn)
    elif kind == "shopping":
        _shopping_ad_groups(g, spec, campaign_rn)
    elif kind == "pmax_retail":
        _pmax_asset_groups(g, spec, campaign_rn, pmax_assets or {})
    return g


def summarize(g: Graph) -> dict[str, int]:
    counts: dict[str, int] = {}
    for op in g.ops:
        which = gads_client.oneof(op, "operation")
        counts[which] = counts.get(which, 0) + 1
    return counts
