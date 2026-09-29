"""Offline tests: spec normalization, graph building, workspace validation. No network."""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gads_build  # noqa: E402
import gads_client  # noqa: E402
import gads_spec  # noqa: E402
import gads_workspace  # noqa: E402

PROFILE = {"login_customer_id": "1234567890", "customer_id": "1112223333", "merchant_id": "123456789",
           "currency": "USD", "timezone": "America/New_York", "budget_cap_major": 200}
API = "v25"


def load(name: str, tag: str = "T1") -> dict:
    raw = json.loads((HERE / "specs" / name).read_text().replace("{tag}", tag))
    for ag in raw.get("asset_groups", []):  # example paths do not exist here: use asset ids
        ag["images"] = {slot: [str(100 + i) for i, _ in enumerate(refs)] for slot, refs in ag["images"].items()}
    return gads_spec.normalize(raw, PROFILE)


def test_specs_and_graphs() -> None:
    client = gads_client.offline_client(API)
    for name, kind, expect in (("example-search.json", "search", {"campaign_operation": 1, "ad_group_operation": 1,
                                                                  "ad_group_criterion_operation": 3,
                                                                  "ad_group_ad_operation": 1, "asset_operation": 1,
                                                                  "ad_group_asset_operation": 1}),
                               ("example-shopping.json", "shopping", {"ad_group_criterion_operation": 3,
                                                                      "ad_group_ad_operation": 1})):
        spec = load(name)
        assert spec["campaign"]["kind"] == kind
        g = gads_build.build_graph(client, PROFILE["customer_id"], spec)
        counts = gads_build.summarize(g)
        for key, val in expect.items():
            assert counts.get(key) == val, (name, key, counts)
        camp = next(o.campaign_operation.create for o in g.ops if gads_client.oneof(o, "operation") == "campaign_operation")
        assert camp.status.name == "PAUSED"
        assert camp.geo_target_type_setting.positive_geo_target_type.name == "PRESENCE"
        assert camp.contains_eu_political_advertising.name == "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"
        assert "T1|" in camp.name
        budget = next(o.campaign_budget_operation.create for o in g.ops
                      if gads_client.oneof(o, "operation") == "campaign_budget_operation")
        assert budget.explicitly_shared is False
        if kind == "search":
            assert camp.network_settings.target_partner_search_network is False
            assert camp.network_settings.target_content_network is False
            assert camp.bidding_strategy_type.name in ("UNSPECIFIED", "MAXIMIZE_CONVERSIONS")
            ads = [o.ad_group_ad_operation.create for o in g.ops if gads_client.oneof(o, "operation") == "ad_group_ad_operation"]
            assert ads[0].status.name == "PAUSED" and len(ads[0].ad.responsive_search_ad.headlines) == 5
            assert ads[0].ad.responsive_search_ad.headlines[0].pinned_field.name == "HEADLINE_1"
        if kind == "shopping":
            assert camp.shopping_setting.merchant_id == 123456789
            assert camp.shopping_setting.campaign_priority == 0
            ags = [o.ad_group_operation.create for o in g.ops if gads_client.oneof(o, "operation") == "ad_group_operation"]
            assert ags[0].type_.name == "SHOPPING_PRODUCT_ADS"
            crits = [o.ad_group_criterion_operation.create for o in g.ops
                     if gads_client.oneof(o, "operation") == "ad_group_criterion_operation"]
            assert crits[0].listing_group.type_.name == "SUBDIVISION"
            assert crits[1].listing_group.case_value.product_brand.value == "Acme" and crits[1].cpc_bid_micros == 600000
            assert crits[2].cpc_bid_micros == 300000 and crits[2].listing_group.parent_ad_group_criterion == crits[0].resource_name
    # pmax: assets phase + graph with placeholders
    spec = load("example-pmax-retail.json")
    g = gads_build.Graph(client, PROFILE["customer_id"])
    asset_ops, mapping = gads_build.pmax_asset_operations(g, spec)
    assert len(asset_ops) == 3 + 1 + 2 + 1, len(asset_ops)  # text assets only; images are existing ids
    assets = gads_build.resolve_existing_assets(g, spec)
    for name, pairs in mapping.items():
        for i, (key, _) in enumerate(pairs):
            assets.setdefault(name, {}).setdefault(key, f"customers/1112223333/assets/{-500 - i}")
    graph = gads_build.build_graph(client, PROFILE["customer_id"], spec, assets)
    counts = gads_build.summarize(graph)
    assert counts["asset_group_operation"] == 1 and counts["asset_group_asset_operation"] == 10, counts
    assert counts["asset_group_listing_group_filter_operation"] == 3 and counts["asset_group_signal_operation"] == 1
    camp = next(o.campaign_operation.create for o in graph.ops if gads_client.oneof(o, "operation") == "campaign_operation")
    assert camp.advertising_channel_type.name == "PERFORMANCE_MAX"
    assert camp.maximize_conversion_value.target_roas == 3.0
    assert camp.asset_automation_settings[0].asset_automation_status.name == "OPTED_OUT"
    assert camp.brand_guidelines_enabled is False
    filters = [o.asset_group_listing_group_filter_operation.create for o in graph.ops
               if gads_client.oneof(o, "operation") == "asset_group_listing_group_filter_operation"]
    assert [f.type_.name for f in filters] == ["SUBDIVISION", "UNIT_INCLUDED", "UNIT_EXCLUDED"]
    assert filters[1].case_value.product_custom_attribute.index.name == "INDEX0"
    assert filters[1].case_value.product_custom_attribute.value == "top10"


def rejected(spec: dict, profile: dict, needle: str) -> None:
    try:
        gads_spec.normalize(spec, profile)
    except gads_spec.SpecError as exc:
        assert needle in str(exc), (needle, str(exc))
        return
    raise AssertionError(f"spec accepted, expected rejection mentioning {needle!r}")


def mutate(base: dict, path: list, value) -> dict:
    out = json.loads(json.dumps(base))
    node = out
    for key in path[:-1]:
        node = node[key]
    if value is Ellipsis:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return out


def test_spec_rejections() -> None:
    base = json.loads((HERE / "specs" / "example-search.json").read_text().replace("{tag}", "x"))
    rejected(mutate(base, ["campaign", "daily_budget_major"], 500), PROFILE, "budget_cap_major")
    rejected(mutate(base, ["currency"], "EUR"), PROFILE, "currency")
    rejected(mutate(base, ["campaign", "eu_political_advertising"], ...), PROFILE, "eu_political")
    rejected(mutate(base, ["campaign", "tracking_url_template"], "https://t.example/?x=1"), PROFILE, "lpurl")
    rejected(mutate(base, ["ad_groups", 0, "ads", 0, "headlines"], ["a", "b"]), PROFILE, "at least 3")
    rejected(mutate(base, ["campaign", "geo", "positive_geo_target_type"], "EVERYONE"), PROFILE, "positive_geo")
    rejected(base, {**PROFILE, "currency": "JPY"}, "currency")
    rejected(mutate(base, ["campaign", "networkk"], {}), PROFILE, "unknown field")
    rejected(mutate(base, ["campaign", "network", "search_partner"], False), PROFILE, "unknown field")
    rejected(mutate(base, ["ad_groups", 0, "ads", 0, "pinned"], {}), PROFILE, "unknown field")
    shop = json.loads((HERE / "specs" / "example-shopping.json").read_text().replace("{tag}", "x"))
    rejected(mutate(shop, ["campaign", "campaign_priority"], 3), PROFILE, "campaign_priority")
    rejected(shop, {k: v for k, v in PROFILE.items() if k != "merchant_id"}, "merchant_id")
    pmax = json.loads((HERE / "specs" / "example-pmax-retail.json").read_text().replace("{tag}", "x"))
    for ag in pmax["asset_groups"]:
        ag["images"] = {k: ["1"] for k in ag["images"]}
    rejected(mutate(pmax, ["campaign", "bidding"], {"strategy": "manual_cpc"}), PROFILE, "not allowed")
    rejected(mutate(pmax, ["asset_groups", 0, "images", "logo"], []), PROFILE, "logo")
    rejected(mutate(pmax, ["asset_groups", 0, "images", "logo"], ["creatives/missing.png"]), PROFILE, "neither")


def test_workspace() -> None:
    ws = json.loads((HERE / "specs" / "example-workspace.json").read_text())
    ws["profiles"] = {"p1": {**PROFILE}}
    ws["defaults"]["profile"] = "p1"
    gads_workspace.validate_workspace(ws)
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "workspace.json"
        path.write_text(json.dumps(ws))
        loaded = gads_workspace.load_workspace(str(path))
        assert loaded.state_dir == (pathlib.Path(tmp) / ".googleops").resolve()
        ws2 = {**ws, "defaults": {**ws["defaults"], "state_dir": "../escape"}}
        path.write_text(json.dumps(ws2))
        escaped = False
        try:
            gads_workspace.load_workspace(str(path))
        except gads_workspace.WorkspaceError:
            escaped = True
        assert escaped, "state_dir escape allowed"
    bad = mutate(ws, ["profiles", "p1", "customer_id"], "123")
    try:
        gads_workspace.validate_workspace(bad)
    except gads_workspace.WorkspaceError:
        return
    raise AssertionError("bad customer id accepted")


def test_client_call_shapes() -> None:
    """Flattened-kwarg names the CLI relies on must exist on the generated clients (no network)."""
    import inspect

    import google.shopping.merchant_accounts_v1 as acc
    from google.protobuf import field_mask_pb2

    client = gads_client.offline_client(API)
    sig = inspect.signature(client.get_service("ProductLinkInvitationService").update_product_link_invitation)
    assert {"customer_id", "resource_name", "product_link_invitation_status"} <= set(sig.parameters)
    op = client.get_type("MutateOperation")
    client.copy_from(op.campaign_operation.update_mask, field_mask_pb2.FieldMask(paths=["status"]))
    assert list(op.campaign_operation.update_mask.paths) == ["status"]
    acc.RetrieveLatestTermsOfServiceRequest(region_code="US", kind=acc.TermsOfServiceKind.MERCHANT_CENTER)
    acc.AcceptTermsOfServiceRequest(name="termsOfService/1", account="accounts/1", region_code="US")
    acc.ClaimHomepageRequest(name="accounts/1/homepage", overwrite=False)
    acc.ProposeAccountServiceRequest(parent="accounts/1", provider="providers/2",
                                     account_service=acc.AccountService(campaigns_management={}, provider="providers/2"))
    pmax = json.loads((HERE / "specs" / "example-pmax-retail.json").read_text().replace("{tag}", "x"))
    for ag in pmax["asset_groups"]:
        ag["images"] = {k: ["1"] for k in ag["images"]}
    aliased = gads_spec.normalize(mutate(pmax, ["campaign", "bidding"], {"strategy": "target_roas", "target_roas": 3.0}),
                                  PROFILE)
    assert aliased["campaign"]["bidding"] == {"strategy": "maximize_conversion_value", "target_roas": 3.0}


def test_sheetfeed_validation() -> None:
    import sheetfeed

    header = sheetfeed.REQUIRED + ["gtin"]
    good = [["sku1", "T", "D", "in_stock", "new", "19.99 USD", "https://x.com/p", "https://x.com/i.jpg", "B", "1234567890123"]]
    assert sheetfeed.validate_rows(header, good, "mc") == []
    meta_row = [["sku1", "T", "D", "in stock", "new", "19.99 USD", "https://x.com/p", "https://x.com/i.jpg", "B", ""]]
    assert sheetfeed.validate_rows(header, meta_row, "meta") == []
    assert any("availability" in p for p in sheetfeed.validate_rows(header, meta_row, "mc"))
    bad = [["sku1", "T", "D", "in_stock", "new", "19.99", "http://x.com/p", "https://x.com/i.jpg", "B", ""],
           ["sku1", "T", "D", "in_stock", "new", "19.99 USD", "https://x.com/p", "https://x.com/i.jpg", "B", ""]]
    problems = sheetfeed.validate_rows(header, bad, "mc")
    assert any("price" in p for p in problems) and any("duplicate id" in p for p in problems)
    assert any("https" in p for p in problems)
    assert sheetfeed.csv_export_url("https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit#gid=5", 5).endswith("gid=5")
    assert "missing required" in sheetfeed.validate_rows(["id", "title"], [], "mc")[0]


if __name__ == "__main__":
    test_specs_and_graphs()
    test_spec_rejections()
    test_workspace()
    test_client_call_shapes()
    test_sheetfeed_validation()
    print("ok")
