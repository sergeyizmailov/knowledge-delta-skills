"""Launch spec validation and normalization.

The agent writes a JSON spec; this module rejects anything the launcher cannot build safely.
All money is entered in major units and converted to micros here; the profile budget cap is the
hard ceiling.
"""

from __future__ import annotations

import re
from typing import Any

SPEC_SCHEMA = "googleops.spec/v1"
KINDS = ("search", "pmax_retail", "shopping")
BIDDING = {
    "search": ("maximize_conversions", "maximize_conversion_value", "manual_cpc", "target_cpa", "target_roas"),
    "pmax_retail": ("maximize_conversions", "maximize_conversion_value"),
    "shopping": ("manual_cpc", "maximize_conversion_value", "target_roas", "maximize_clicks"),
}
MATCH_TYPES = ("EXACT", "PHRASE", "BROAD")
GEO_TYPES = ("PRESENCE", "PRESENCE_OR_INTEREST", "SEARCH_INTEREST")
LISTING_DIMENSIONS = ("brand", "item_id", "product_type", "category", "condition", "channel",
                      "custom_label_0", "custom_label_1", "custom_label_2", "custom_label_3", "custom_label_4")
NO_MINOR_UNITS = {"JPY", "KRW", "VND", "CLP", "ISK", "HUF", "TWD", "UGX", "PYG", "RWF", "XAF", "XOF"}
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
RSA_LIMITS = {"headlines": (3, 15, 30), "descriptions": (2, 4, 90)}
PMAX_MIN = {"headlines": 3, "long_headlines": 1, "descriptions": 2}
PMAX_TEXT_MAX = {"headlines": 30, "long_headlines": 90, "descriptions": 90}


class SpecError(Exception):
    pass


def micros(value: Any, label: str, currency: str) -> int:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise SpecError(f"{label} must be a positive number in major units")
    if currency in NO_MINOR_UNITS and float(value) != int(value):
        raise SpecError(f"{label}: {currency} has no minor units; use whole numbers")
    return int(round(float(value) * 1_000_000))


ALLOWED = {
    "spec": {"schema", "run_id", "currency", "campaign", "ad_groups", "asset_groups", "profile"},
    "campaign": {"kind", "name", "daily_budget_major", "bidding", "geo", "languages", "network",
                 "eu_political_advertising", "tracking_url_template", "final_url_suffix", "start_date",
                 "negative_keywords", "merchant_id", "feed_label", "campaign_priority", "enable_local",
                 "final_url_expansion", "brand_exclusion_shared_set_id"},
    "bidding": {"strategy", "target_cpa_major", "target_roas", "enhanced_cpc", "cpc_bid_ceiling_major"},
    "geo": {"locations", "positive_geo_target_type"},
    "network": {"search_partners", "content"},
    "ad_group": {"name", "cpc_bid_major", "keywords", "ads", "sitelinks", "listing_groups"},
    "ad": {"final_urls", "headlines", "descriptions", "path1", "path2", "pins"},
    "asset_group": {"name", "final_urls", "headlines", "long_headlines", "descriptions", "business_name", "images",
                    "search_themes", "audience_ids", "listing_filter"},
    "listing": {"dimension", "units", "others"},
    "images": {"marketing", "square", "logo", "portrait"},
}


def _strict(obj: Any, kind: str, label: str) -> None:
    """Unknown keys are rejected: a misspelled safety field must not produce a green plan."""
    if not isinstance(obj, dict):
        raise SpecError(f"{label} must be an object")
    unknown = {k for k in obj if not str(k).startswith("_")} - ALLOWED[kind]
    if unknown:
        raise SpecError(f"{label}: unknown field(s) {sorted(unknown)}; allowed: {sorted(ALLOWED[kind])}")


def _image_ref(value: str, label: str) -> str:
    import pathlib
    if str(value).isdigit():
        return str(value)
    if pathlib.Path(str(value)).expanduser().is_file():
        return str(value)
    raise SpecError(f"{label}: {value!r} is neither an existing file nor a numeric asset id")


def _require(obj: dict[str, Any], key: str, label: str) -> Any:
    if key not in obj:
        raise SpecError(f"{label}: missing {key}")
    return obj[key]


def _text_list(values: Any, label: str, minimum: int, maximum: int | None, max_len: int) -> list[str]:
    if not isinstance(values, list) or len(values) < minimum:
        raise SpecError(f"{label}: at least {minimum} entries required")
    if maximum is not None and len(values) > maximum:
        raise SpecError(f"{label}: at most {maximum} entries allowed")
    out = []
    for item in values:
        text = str(item).strip()
        if not text or len(text) > max_len:
            raise SpecError(f"{label}: {text[:40]!r} must be 1-{max_len} chars")
        out.append(text)
    if len(set(out)) != len(out):
        raise SpecError(f"{label}: duplicates are rejected by the API")
    return out


def _urls(values: Any, label: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise SpecError(f"{label}: final_urls required")
    for url in values:
        if not re.match(r"^https?://", str(url)):
            raise SpecError(f"{label}: final URL must be absolute: {url}")
    return [str(u) for u in values]


def _bidding(camp: dict[str, Any], kind: str, currency: str) -> dict[str, Any]:
    bid = _require(camp, "bidding", "campaign")
    _strict(bid, "bidding", "campaign.bidding")
    strategy = _require(bid, "strategy", "campaign.bidding")
    if kind == "pmax_retail" and strategy == "target_roas" and "target_roas" in bid:
        strategy = "maximize_conversion_value"  # PMax has no standalone tROAS strategy; alias
    if kind == "pmax_retail" and strategy == "target_cpa" and "target_cpa_major" in bid:
        strategy = "maximize_conversions"
    if strategy not in BIDDING[kind]:
        raise SpecError(f"campaign.bidding.strategy {strategy} not allowed for {kind}: {BIDDING[kind]}")
    out: dict[str, Any] = {"strategy": strategy}
    if strategy == "target_cpa":
        out["target_cpa_micros"] = micros(_require(bid, "target_cpa_major", "bidding"), "target_cpa_major", currency)
    if strategy == "target_roas":
        roas = _require(bid, "target_roas", "bidding")
        if not isinstance(roas, (int, float)) or roas <= 0:
            raise SpecError("bidding.target_roas must be a positive ratio (3.0 = 300%)")
        out["target_roas"] = float(roas)
    if strategy in ("maximize_conversions",) and "target_cpa_major" in bid:
        out["target_cpa_micros"] = micros(bid["target_cpa_major"], "target_cpa_major", currency)
    if strategy in ("maximize_conversion_value",) and "target_roas" in bid:
        out["target_roas"] = float(bid["target_roas"])
    if strategy == "manual_cpc":
        out["enhanced_cpc"] = bool(bid.get("enhanced_cpc", False))
    if "cpc_bid_ceiling_major" in bid:
        out["cpc_bid_ceiling_micros"] = micros(bid["cpc_bid_ceiling_major"], "cpc_bid_ceiling_major", currency)
    return out


def _listing_groups(node: Any, label: str, currency: str, kind: str) -> dict[str, Any] | None:
    if node is None:
        return None
    _strict(node, "listing", label)
    dim = _require(node, "dimension", label)
    if dim not in LISTING_DIMENSIONS:
        raise SpecError(f"{label}: dimension must be one of {LISTING_DIMENSIONS}")
    units = node.get("units", [])
    if not isinstance(units, list):
        raise SpecError(f"{label}: units must be a list")
    out_units = []
    for unit in units:
        value = str(_require(unit, "value", f"{label}.units"))
        entry: dict[str, Any] = {"value": value}
        if kind == "shopping":
            if unit.get("exclude"):
                entry["exclude"] = True
            elif "cpc_bid_major" in unit:
                entry["cpc_bid_micros"] = micros(unit["cpc_bid_major"], f"{label}.units.cpc_bid_major", currency)
        out_units.append(entry)
    others = node.get("others", "exclude")
    if kind == "shopping":
        if isinstance(others, dict) and "cpc_bid_major" in others:
            others = {"cpc_bid_micros": micros(others["cpc_bid_major"], f"{label}.others.cpc_bid_major", currency)}
        elif others != "exclude":
            raise SpecError(f"{label}: others must be 'exclude' or {{cpc_bid_major}}")
    else:
        if others not in ("exclude",):
            raise SpecError(f"{label}: pmax listing filter others must be 'exclude' (include = omit listing_filter)")
    if not out_units and kind == "pmax_retail":
        raise SpecError(f"{label}: listing_filter needs at least one unit or omit it to include all products")
    return {"dimension": dim, "units": out_units, "others": others}


def normalize(raw: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("schema") != SPEC_SCHEMA:
        raise SpecError(f"spec.schema must be {SPEC_SCHEMA}")
    _strict(raw, "spec", "spec")
    run_id = str(_require(raw, "run_id", "spec"))
    if not RUN_ID.match(run_id):
        raise SpecError("run_id: letters, digits, . _ - only, max 80 chars")
    currency = str(_require(raw, "currency", "spec")).upper()
    if currency != str(profile["currency"]).upper():
        raise SpecError(f"spec.currency {currency} != profile currency {profile['currency']} — wrong account?")
    camp = _require(raw, "campaign", "spec")
    _strict(camp, "campaign", "campaign")
    kind = _require(camp, "kind", "campaign")
    if kind not in KINDS:
        raise SpecError(f"campaign.kind must be one of {KINDS}")
    name = str(_require(camp, "name", "campaign")).strip()
    if not name or len(name) > 255:
        raise SpecError("campaign.name must be 1-255 chars")
    budget = micros(_require(camp, "daily_budget_major", "campaign"), "daily_budget_major", currency)
    cap = micros(profile["budget_cap_major"], "profile.budget_cap_major", currency)
    if budget > cap:
        raise SpecError(
            f"daily_budget_major {camp['daily_budget_major']} exceeds profile budget_cap_major "
            f"{profile['budget_cap_major']} {currency}; raise the cap deliberately in workspace.json")
    geo = _require(camp, "geo", "campaign")
    _strict(geo, "geo", "campaign.geo")
    locations = _require(geo, "locations", "campaign.geo")
    if not isinstance(locations, list) or not locations or not all(str(x).isdigit() for x in locations):
        raise SpecError("campaign.geo.locations must be numeric geo target constant ids (US = 2840)")
    geo_type = geo.get("positive_geo_target_type", "PRESENCE")
    if geo_type not in GEO_TYPES:
        raise SpecError(f"campaign.geo.positive_geo_target_type must be one of {GEO_TYPES}")
    languages = camp.get("languages", [])
    if not isinstance(languages, list) or not all(str(x).isdigit() for x in languages):
        raise SpecError("campaign.languages must be numeric language constant ids (English = 1000)")
    if "eu_political_advertising" not in camp or not isinstance(camp["eu_political_advertising"], bool):
        raise SpecError("campaign.eu_political_advertising must be explicit true/false (required declaration)")
    network = camp.get("network", {})
    _strict(network, "network", "campaign.network")
    out_campaign: dict[str, Any] = {
        "kind": kind,
        "name": name,
        "daily_budget_micros": budget,
        "bidding": _bidding(camp, kind, currency),
        "locations": [str(x) for x in locations],
        "positive_geo_target_type": geo_type,
        "languages": [str(x) for x in languages],
        "eu_political_advertising": camp["eu_political_advertising"],
        "tracking_url_template": camp.get("tracking_url_template"),
        "final_url_suffix": camp.get("final_url_suffix"),
        "search_partners": bool(network.get("search_partners", False)),
        "content_network": bool(network.get("content", False)),
        "start_date": camp.get("start_date"),
        "negative_keywords": [],
    }
    for neg in camp.get("negative_keywords", []):
        text = str(_require(neg, "text", "negative_keywords"))
        match = str(neg.get("match_type", "PHRASE")).upper()
        if match not in MATCH_TYPES:
            raise SpecError(f"negative_keywords.match_type must be one of {MATCH_TYPES}")
        out_campaign["negative_keywords"].append({"text": text, "match_type": match})
    tmpl = out_campaign["tracking_url_template"]
    if tmpl and "{lpurl}" not in tmpl and "{unescapedlpurl}" not in tmpl and "{escapedlpurl}" not in tmpl:
        raise SpecError("tracking_url_template must contain {lpurl} (or an escaped variant)")
    if kind in ("pmax_retail", "shopping"):
        merchant = camp.get("merchant_id", profile.get("merchant_id"))
        if not merchant or not str(merchant).isdigit():
            raise SpecError(f"{kind}: merchant_id required (spec.campaign.merchant_id or profile.merchant_id)")
        out_campaign["merchant_id"] = int(merchant)
        out_campaign["feed_label"] = camp.get("feed_label")
    if kind == "shopping":
        prio = camp.get("campaign_priority", 0)
        if prio not in (0, 1, 2):
            raise SpecError("campaign_priority must be 0, 1 or 2")
        out_campaign["campaign_priority"] = prio
        out_campaign["enable_local"] = bool(camp.get("enable_local", False))
    if kind == "pmax_retail":
        out_campaign["final_url_expansion"] = bool(camp.get("final_url_expansion", False))
        out_campaign["brand_exclusion_shared_set_id"] = camp.get("brand_exclusion_shared_set_id")
        if out_campaign["brand_exclusion_shared_set_id"] is not None and not str(
                out_campaign["brand_exclusion_shared_set_id"]).isdigit():
            raise SpecError("brand_exclusion_shared_set_id must be a numeric shared set id")

    out: dict[str, Any] = {"schema": SPEC_SCHEMA, "run_id": run_id, "currency": currency,
                           "campaign": out_campaign, "ad_groups": [], "asset_groups": []}

    if kind == "pmax_retail":
        groups = _require(raw, "asset_groups", "spec")
        if not isinstance(groups, list) or not groups:
            raise SpecError("pmax_retail: asset_groups must have at least one entry")
        for i, ag in enumerate(groups):
            label = f"asset_groups[{i}]"
            _strict(ag, "asset_group", label)
            entry = {
                "name": str(_require(ag, "name", label)).strip(),
                "final_urls": _urls(_require(ag, "final_urls", label), label),
                "headlines": _text_list(_require(ag, "headlines", label), f"{label}.headlines",
                                        PMAX_MIN["headlines"], 15, PMAX_TEXT_MAX["headlines"]),
                "long_headlines": _text_list(_require(ag, "long_headlines", label), f"{label}.long_headlines",
                                             PMAX_MIN["long_headlines"], 5, PMAX_TEXT_MAX["long_headlines"]),
                "descriptions": _text_list(_require(ag, "descriptions", label), f"{label}.descriptions",
                                           PMAX_MIN["descriptions"], 5, PMAX_TEXT_MAX["descriptions"]),
                "business_name": str(_require(ag, "business_name", label))[:25],
                "images": {},
                "search_themes": _text_list(ag.get("search_themes", []), f"{label}.search_themes", 0, 25, 80),
                "audience_ids": [str(x) for x in ag.get("audience_ids", [])],
                "listing_filter": _listing_groups(ag.get("listing_filter"), f"{label}.listing_filter",
                                                  currency, kind),
            }
            images = ag.get("images", {})
            _strict(images, "images", f"{label}.images")
            for slot in ("marketing", "square", "logo", "portrait"):
                items = images.get(slot, [])
                if not isinstance(items, list):
                    raise SpecError(f"{label}.images.{slot} must be a list of local paths or asset ids")
                entry["images"][slot] = [_image_ref(x, f"{label}.images.{slot}") for x in items]
            if not entry["images"]["marketing"] or not entry["images"]["square"] or not entry["images"]["logo"]:
                raise SpecError(f"{label}.images needs at least one marketing, one square and one logo image "
                                "(local file path or existing asset id)")
            out["asset_groups"].append(entry)
        if raw.get("ad_groups"):
            raise SpecError("pmax_retail has asset_groups, not ad_groups")
        return out

    groups = _require(raw, "ad_groups", "spec")
    if not isinstance(groups, list) or not groups:
        raise SpecError("ad_groups must have at least one entry")
    for i, ag in enumerate(groups):
        label = f"ad_groups[{i}]"
        _strict(ag, "ad_group", label)
        entry: dict[str, Any] = {"name": str(_require(ag, "name", label)).strip(), "keywords": [], "ads": []}
        if "cpc_bid_major" in ag:
            entry["cpc_bid_micros"] = micros(ag["cpc_bid_major"], f"{label}.cpc_bid_major", currency)
        if kind == "search":
            kws = _require(ag, "keywords", label)
            if not isinstance(kws, list) or not kws:
                raise SpecError(f"{label}: keywords required for search")
            for kw in kws:
                text = str(_require(kw, "text", f"{label}.keywords")).strip()
                match = str(_require(kw, "match_type", f"{label}.keywords")).upper()
                if match not in MATCH_TYPES:
                    raise SpecError(f"{label}.keywords.match_type must be one of {MATCH_TYPES}")
                if len(text.split()) > 10 or len(text) > 80:
                    raise SpecError(f"{label}: keyword too long: {text!r}")
                k: dict[str, Any] = {"text": text, "match_type": match}
                if "cpc_bid_major" in kw:
                    k["cpc_bid_micros"] = micros(kw["cpc_bid_major"], f"{label}.keywords.cpc_bid_major", currency)
                entry["keywords"].append(k)
            ads = _require(ag, "ads", label)
            if not isinstance(ads, list) or not ads:
                raise SpecError(f"{label}: at least one RSA required")
            for j, ad in enumerate(ads):
                alabel = f"{label}.ads[{j}]"
                _strict(ad, "ad", alabel)
                hmin, hmax, hlen = RSA_LIMITS["headlines"]
                dmin, dmax, dlen = RSA_LIMITS["descriptions"]
                a = {
                    "final_urls": _urls(_require(ad, "final_urls", alabel), alabel),
                    "headlines": _text_list(_require(ad, "headlines", alabel), f"{alabel}.headlines", hmin, hmax, hlen),
                    "descriptions": _text_list(_require(ad, "descriptions", alabel), f"{alabel}.descriptions",
                                               dmin, dmax, dlen),
                    "path1": str(ad.get("path1", ""))[:15] or None,
                    "path2": str(ad.get("path2", ""))[:15] or None,
                    "pins": ad.get("pins", {}),
                }
                if a["path2"] and not a["path1"]:
                    raise SpecError(f"{alabel}: path2 requires path1")
                entry["ads"].append(a)
            entry["sitelinks"] = []
            for sl in ag.get("sitelinks", []):
                entry["sitelinks"].append({
                    "link_text": str(_require(sl, "link_text", f"{label}.sitelinks"))[:25],
                    "final_urls": _urls(_require(sl, "final_urls", f"{label}.sitelinks"), f"{label}.sitelinks"),
                    "description1": str(sl.get("description1", ""))[:35] or None,
                    "description2": str(sl.get("description2", ""))[:35] or None,
                })
        else:  # shopping
            entry["listing_groups"] = _listing_groups(ag.get("listing_groups"), f"{label}.listing_groups",
                                                      currency, kind)
            if entry["listing_groups"] is None:
                entry["listing_groups"] = {"dimension": None, "units": [], "others": {
                    "cpc_bid_micros": entry.get("cpc_bid_micros") or micros(
                        _require(ag, "cpc_bid_major", label), f"{label}.cpc_bid_major", currency)}}
        out["ad_groups"].append(entry)
    return out
