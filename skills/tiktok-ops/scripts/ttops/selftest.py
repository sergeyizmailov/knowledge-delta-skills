"""Offline test suite. No token, no network.

Run:  PYTHONPATH=scripts python3 -m ttops.selftest
Every test asserts a behaviour that, if it regressed, would cost real money or
create a live campaign nobody approved.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from decimal import Decimal

from . import api, lifecycle, mcp as mcp_mod, money, spec as spec_mod
from .api import Client, TransportError, is_write
from .errors import explain, explain_status
from .lifecycle import Lock, State
from .workspace import Workspace, WorkspaceError

PASS, FAIL = [], []


def check(name, fn):
    try:
        fn()
        PASS.append(name)
    except AssertionError as exc:
        FAIL.append(f"{name}: {exc}")
    except Exception as exc:  # noqa: BLE001
        FAIL.append(f"{name}: unexpected {type(exc).__name__}: {exc}")


def raises(exc_type, fn, contains=None):
    try:
        fn()
    except exc_type as exc:
        if contains and contains.lower() not in str(exc).lower():
            raise AssertionError(f"expected message containing {contains!r}, got {exc}")
        return
    raise AssertionError(f"expected {exc_type.__name__}, nothing raised")


PROFILE = {"_name": "main", "advertiser_id": "7000000000000000001",
           "currency": "USD", "timezone": "America/New_York",
           "pixel_id": "CABC123"}


def base_spec(**over):
    spec = {
        "schema": spec_mod.SCHEMA_VERSION,
        "currency": "USD",
        "campaign": {
            "campaign_name": "test-campaign",
            "objective_type": "TRAFFIC",
            "special_industries": [],
            "budget_mode": "BUDGET_MODE_DAY",
            "budget": 100,
        },
        "adgroups": [{
            "adgroup_name": "ag-1",
            "optimization_goal": "CLICK",
            "billing_event": "CPC",
            "pacing": "PACING_MODE_SMOOTH",
            "bid_type": "BID_TYPE_NO_BID",
            "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
            "promotion_type": "WEBSITE",
            "schedule_type": "SCHEDULE_FROM_NOW",
            "schedule_start_time": "2026-09-20 07:00:00",
            "budget_mode": "BUDGET_MODE_DAY",
            "budget": 50,
            "creatives": [{
                "ad_name": "ad-1", "ad_format": "SINGLE_VIDEO",
                "identity_type": "CUSTOMIZED_USER", "video_id": "v1",
                "landing_page_url": "https://example.com",
            }],
        }],
    }
    spec.update(over)
    return spec


def cbo_spec():
    """Same shape with Campaign Budget Optimization on: budget moves to the campaign
    and TikTok overrides pacing itself."""
    spec = base_spec()
    spec["campaign"]["budget_optimize_on"] = True
    spec["campaign"]["budget_mode"] = "BUDGET_MODE_DAY"
    spec["campaign"]["budget"] = 100
    ag = spec["adgroups"][0]
    for key in ("budget", "budget_mode", "pacing"):
        ag.pop(key, None)
    return spec


class _FakeClient(Client):
    """A Client whose transport is a queue of canned response bodies."""

    def __init__(self, payloads):
        super().__init__(token="x", allow_writes=True)
        self._payloads = list(payloads)

    def _request(self, method, path, params=None, body=None):
        return self._payloads.pop(0), 200


# -- money -------------------------------------------------------------------

def t_usd_bounds():
    low, high = money.bounds("USD", "adgroup")
    assert low == Decimal("20"), low
    low, _ = money.bounds("USD", "campaign")
    assert low == Decimal("50"), low


def t_jpy_ratio():
    low, _ = money.bounds("JPY", "adgroup")
    assert low == Decimal("2000"), f"JPY adgroup min should be 20*100, got {low}"
    assert money.decimals_for("JPY") == 0


def t_idr_ratio():
    low, _ = money.bounds("IDR", "adgroup")
    assert low == Decimal("200000"), low


def t_integer_currency_rejects_decimals():
    raises(money.BudgetError, lambda: money.validate(2000.50, "JPY", "adgroup"),
           "whole units")


def t_usd_template_on_jpy_account_rejected():
    # The 100x scenario: a 50-unit USD budget landing on a JPY account.
    raises(money.BudgetError, lambda: money.validate(50, "JPY", "adgroup"), "below")


def t_below_min_rejected():
    raises(money.BudgetError, lambda: money.validate(5, "USD", "adgroup"), "below")


def t_store_source_lower_min():
    money.validate(10, "USD", "adgroup", store_product_source=True)


def t_absurd_budget_rejected():
    raises(money.BudgetError, lambda: money.validate(99_000_000, "USD", "adgroup"),
           "maximum")


def t_quantize_rounds_down():
    assert money.quantize("10.999", "USD") == Decimal("10.99")


def t_105_floor():
    # spend 100 -> floor 105; 104 must fail, 105 must pass
    raises(money.BudgetError,
           lambda: money.check_update(104, 100, "USD", "adgroup"), "105%")
    assert money.check_update(105, 100, "USD", "adgroup") == Decimal("105.00")


def t_unknown_currency():
    raises(money.BudgetError, lambda: money.currency_info("XYZ"), "unknown currency")


def t_describe_names_currency():
    assert money.describe(1234.5, "USD") == "1,234.50 USD"
    assert money.describe(1234, "JPY") == "1,234 JPY"


# -- spec --------------------------------------------------------------------

def t_valid_spec_passes():
    assert spec_mod.validate(base_spec(), PROFILE) == []


def t_everything_created_disabled():
    plan = spec_mod.normalize(base_spec(), PROFILE)
    assert plan["campaign"]["operation_status"] == "DISABLE"
    for ag in plan["adgroups"]:
        assert ag["payload"]["operation_status"] == "DISABLE"
    ad = spec_mod.ad_payload("1", "2", plan["adgroups"][0]["creatives"])
    assert ad["operation_status"] == "DISABLE"


def t_disable_cannot_be_overridden():
    # An operator-supplied ENABLE must not survive normalisation.
    s = base_spec()
    s["campaign"]["operation_status"] = "ENABLE"
    s["adgroups"][0]["operation_status"] = "ENABLE"
    plan = spec_mod.normalize(s, PROFILE)
    assert plan["campaign"]["operation_status"] == "DISABLE"
    assert plan["adgroups"][0]["payload"]["operation_status"] == "DISABLE"


def t_currency_mismatch_rejected():
    s = base_spec(currency="EUR")
    errs = spec_mod.validate(s, PROFILE)
    assert any("!= account currency" in e for e in errs), errs


def t_missing_currency_rejected():
    s = base_spec()
    del s["currency"]
    assert any("spec.currency is required" in e for e in spec_mod.validate(s, PROFILE))


def t_filter_only_goal_rejected():
    s = base_spec()
    s["adgroups"][0]["optimization_goal"] = "GMV"
    assert any("reporting filter" in e for e in spec_mod.validate(s, PROFILE))


def t_deprecated_goal_rejected():
    s = base_spec()
    s["adgroups"][0]["optimization_goal"] = "PROFILE_VIEWS"
    assert any("PAGE_VISIT" in e for e in spec_mod.validate(s, PROFILE))


def t_meta_bid_vocabulary_rejected():
    s = base_spec()
    s["adgroups"][0]["bid_type"] = "LOWEST_COST_WITH_BID_CAP"
    errs = spec_mod.validate(s, PROFILE)
    assert any("exactly two" in e for e in errs), errs


def t_cost_cap_needs_price():
    s = base_spec()
    s["adgroups"][0]["bid_type"] = "BID_TYPE_CUSTOM"
    assert any("bid_price is required" in e for e in spec_mod.validate(s, PROFILE))


def t_no_bid_forbids_price():
    s = base_spec()
    s["adgroups"][0]["bid_price"] = 3.0
    assert any("must be omitted" in e for e in spec_mod.validate(s, PROFILE))


def t_cbo_forbids_adgroup_budget():
    s = base_spec()
    s["campaign"]["budget_optimize_on"] = True
    errs = spec_mod.validate(s, PROFILE)
    assert any("ad-group budgets are ignored" in e for e in errs), errs


def t_cbo_valid_shape():
    s = base_spec()
    s["campaign"]["budget_optimize_on"] = True
    s["adgroups"][0].pop("budget")
    s["adgroups"][0].pop("budget_mode")
    assert spec_mod.validate(s, PROFILE) == [], spec_mod.validate(s, PROFILE)
    plan = spec_mod.normalize(s, PROFILE)
    assert plan["campaign"]["budget_optimize_on"] is True
    assert "budget" not in plan["adgroups"][0]["payload"]


def t_campaign_day_forbids_adgroup_lifetime():
    s = base_spec()
    s["adgroups"][0]["budget_mode"] = "BUDGET_MODE_TOTAL"
    s["adgroups"][0]["schedule_type"] = "SCHEDULE_START_END"
    s["adgroups"][0]["schedule_end_time"] = "2026-10-01 07:00:00"
    errs = spec_mod.validate(s, PROFILE)
    assert any("forbids an ad-group lifetime budget" in e for e in errs), errs


def t_continuous_delivery_forbids_lifetime():
    s = base_spec()
    s["campaign"]["budget_mode"] = "BUDGET_MODE_INFINITE"
    s["campaign"].pop("budget")
    s["adgroups"][0]["budget_mode"] = "BUDGET_MODE_TOTAL"
    errs = spec_mod.validate(s, PROFILE)
    assert any("continuous delivery" in e for e in errs), errs


def t_special_industries_must_be_explicit():
    s = base_spec()
    del s["campaign"]["special_industries"]
    assert any("explicitly" in e for e in spec_mod.validate(s, PROFILE))


def t_start_time_required():
    s = base_spec()
    del s["adgroups"][0]["schedule_start_time"]
    assert any("schedule_start_time is required" in e for e in spec_mod.validate(s, PROFILE))


def t_no_sales_enum():
    s = base_spec()
    s["campaign"]["objective_type"] = "SALES"
    errs = spec_mod.validate(s, PROFILE)
    assert any("no SALES enum" in e for e in errs), errs


def t_app_promotion_needs_type():
    s = base_spec()
    s["campaign"]["objective_type"] = "APP_PROMOTION"
    assert any("app_promotion_type is required" in e for e in spec_mod.validate(s, PROFILE))


def t_goal_owning_event_rejects_explicit_event():
    s = base_spec()
    s["adgroups"][0]["optimization_goal"] = "ENGAGED_VIEW"
    s["adgroups"][0]["optimization_event"] = "SOMETHING"
    assert any("sets optimization_event itself" in e for e in spec_mod.validate(s, PROFILE))


def t_global_app_bundle_lpv_conflict():
    s = base_spec()
    s["adgroups"][0]["placement_type"] = "PLACEMENT_TYPE_NORMAL"
    s["adgroups"][0]["placements"] = ["PLACEMENT_GLOBAL_APP_BUNDLE"]
    s["adgroups"][0]["optimization_goal"] = "TRAFFIC_LANDING_PAGE_VIEW"
    errs = spec_mod.validate(s, PROFILE)
    assert any("Global App Bundle" in e for e in errs), errs


def t_duplicate_adgroup_names():
    s = base_spec()
    s["adgroups"].append(json.loads(json.dumps(s["adgroups"][0])))
    assert any("duplicated" in e for e in spec_mod.validate(s, PROFILE))


def t_video_id_required_for_video():
    s = base_spec()
    del s["adgroups"][0]["creatives"][0]["video_id"]
    assert any("video_id is required" in e for e in spec_mod.validate(s, PROFILE))


def t_identity_id_required_for_tt_user():
    s = base_spec()
    s["adgroups"][0]["creatives"][0]["identity_type"] = "TT_USER"
    assert any("identity_id is required" in e for e in spec_mod.validate(s, PROFILE))


def t_normalize_raises_on_invalid():
    raises(spec_mod.SpecError, lambda: spec_mod.normalize(base_spec(currency="EUR"), PROFILE),
           "spec rejected")


def t_total_daily_cbo():
    s = base_spec()
    s["campaign"]["budget_optimize_on"] = True
    s["adgroups"][0].pop("budget")
    s["adgroups"][0].pop("budget_mode")
    plan = spec_mod.normalize(s, PROFILE)
    assert spec_mod.total_daily(plan) == Decimal("100")


def t_total_daily_abo():
    plan = spec_mod.normalize(base_spec(), PROFILE)
    assert spec_mod.total_daily(plan) == Decimal("50")


# -- api transport -----------------------------------------------------------

def t_write_detection():
    assert is_write("/campaign/create/")
    assert is_write("/adgroup/status/update/")
    assert not is_write("/campaign/get/")
    assert not is_write("/report/integrated/get/")


def t_readonly_client_refuses_write():
    c = Client(token="x", allow_writes=False)
    raises(TransportError, lambda: c.post("/campaign/create/", {}), "read-only")


def t_missing_token_is_clear():
    c = Client(token="", allow_writes=False)
    raises(TransportError, lambda: c.get("/campaign/get/"), "no access token")


def t_dry_run_makes_no_call():
    c = Client(token="x", allow_writes=True, dry_run=True)
    out = c.post("/campaign/create/", {"a": 1})
    assert out["_dry_run"] is True


# -- workspace ---------------------------------------------------------------

def t_workspace_rejects_int_advertiser_id():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "workspace.json")
        json.dump({"schema": "ttops.workspace/v1",
                   "profiles": {"m": {"advertiser_id": 123, "currency": "USD",
                                      "timezone": "UTC"}}}, open(path, "w"))
        raises(WorkspaceError, lambda: Workspace.load(explicit=path), "must be a STRING")


def t_workspace_blocked_account():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "workspace.json")
        json.dump({"schema": "ttops.workspace/v1",
                   "blocked_advertiser_ids": ["999"],
                   "profiles": {"m": {"advertiser_id": "999", "currency": "USD",
                                      "timezone": "UTC"}}}, open(path, "w"))
        raises(WorkspaceError, lambda: Workspace.load(explicit=path), "blocked")


def t_workspace_requires_profile_choice():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "workspace.json")
        json.dump({"schema": "ttops.workspace/v1",
                   "profiles": {"a": {"advertiser_id": "1", "currency": "USD", "timezone": "UTC"},
                                "b": {"advertiser_id": "2", "currency": "USD", "timezone": "UTC"}}},
                  open(path, "w"))
        ws = Workspace.load(explicit=path)
        raises(WorkspaceError, lambda: ws.profile(None), "no default_profile")


# -- state and lock ----------------------------------------------------------

def t_lock_is_exclusive():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "state.json")
        with Lock(path):
            raises(RuntimeError, lambda: Lock(path).__enter__(), "owns this state")


def t_state_in_flight_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        st = State(os.path.join(d, "state.json"))
        st.mark_in_flight("campaign:x", {"a": 1})
        assert "campaign:x" in st.data["in_flight"]
        st.record("campaign:x", {"campaign_id": "1"})
        assert "campaign:x" not in st.data["in_flight"]
        assert st.get("campaign:x")["campaign_id"] == "1"


def t_receipt_ttl():
    with tempfile.TemporaryDirectory() as d:
        st = State(os.path.join(d, "state.json"))
        st.receipt("doctor", {"advertiser_id": "1"})
        ok, _ = st.receipt_valid("doctor", 3600, advertiser_id="1")
        assert ok
        ok, why = st.receipt_valid("doctor", 3600, advertiser_id="2")
        assert not ok and "not" in why
        st.data["receipts"]["doctor"]["at"] -= 7200  # age it past any sane TTL
        ok, why = st.receipt_valid("doctor", 3600, advertiser_id="1")
        assert not ok and "old" in why, why
        ok, why = st.receipt_valid("verify", 3600)
        assert not ok and "no verify receipt" in why


# -- errors ------------------------------------------------------------------

def t_error_catalog():
    assert "Throttled" in explain(40100)["cause"]
    assert explain(40105)["escalate"] is True
    assert explain(40901)["escalate"] is False
    assert "do NOT expire" in explain(40102)["action"]
    assert explain(999999)["cause"] == "Unknown code"


# -- mcp companion -----------------------------------------------------------

def t_preflight_emits_disable_everywhere():
    out = mcp_mod.preflight(base_spec(), PROFILE)
    assert out["calls"][0]["arguments"]["operation_status"] == "DISABLE"
    for call in out["calls"]:
        assert call["arguments"].get("operation_status") == "DISABLE", call["tool"]


def t_preflight_tool_order():
    out = mcp_mod.preflight(base_spec(), PROFILE)
    assert [c["tool"] for c in out["calls"]] == \
        ["campaign_create", "adgroup_create", "ad_create"]


def t_preflight_rejects_bad_spec():
    raises(spec_mod.SpecError,
           lambda: mcp_mod.preflight(base_spec(currency="EUR"), PROFILE), "spec rejected")


def t_preflight_states_total_daily():
    out = mcp_mod.preflight(base_spec(), PROFILE)
    assert out["total_daily"] == "50.00 USD"


def t_audit_catches_live_campaign():
    actual = {"campaign": {"list": [{"campaign_id": "1", "operation_status": "ENABLE"}]}}
    res = mcp_mod.audit(actual)
    assert not res["ok"]
    assert res["worst_severity"] == "SPENDING", res


def t_audit_merges_all_three_levels():
    # Regression: an early _rows returned on the FIRST container key, silently
    # dropping campaign and ads from a combined file.
    actual = {
        "campaign": {"list": [{"campaign_id": "1", "operation_status": "DISABLE"}]},
        "adgroups": {"list": [{"adgroup_id": "2", "operation_status": "DISABLE",
                               "schedule_start_time": "2026-09-20 07:00:00"}]},
        "ads": {"list": [{"ad_id": "3", "operation_status": "DISABLE"}]},
    }
    res = mcp_mod.audit(actual)
    assert res["objects_seen"] == {"campaign": 1, "adgroup": 1, "ad": 1}, res["objects_seen"]


def t_audit_catches_currency_floor():
    actual = {"list": [{"adgroup_id": "2", "operation_status": "DISABLE", "budget": 500,
                        "schedule_start_time": "x"}]}
    res = mcp_mod.audit(actual, profile={"currency": "JPY"})
    assert any(f["severity"] == "MONEY" for f in res["findings"]), res["findings"]


def t_audit_detects_drift_from_spec():
    actual = {
        "campaign": {"list": [{"campaign_id": "1", "campaign_name": "test-campaign",
                               "objective_type": "TRAFFIC", "operation_status": "DISABLE",
                               "budget_mode": "BUDGET_MODE_DAY", "budget": 100}]},
        "adgroups": {"list": [{"adgroup_id": "2", "adgroup_name": "ag-1",
                               "optimization_goal": "CLICK", "operation_status": "DISABLE",
                               "billing_event": "CPC", "budget": 999,
                               "schedule_start_time": "2026-09-20 07:00:00"}]},
    }
    res = mcp_mod.audit(actual, base_spec(), PROFILE)
    drift = [f for f in res["findings"] if f["severity"] == "DRIFT" and f["field"] == "budget"]
    assert drift, res["findings"]


def t_audit_no_spec_still_works():
    res = mcp_mod.audit({"list": [{"ad_id": "3", "operation_status": "DISABLE"}]})
    assert res["compared_against_spec"] is False
    assert res["objects_seen"]["ad"] == 1
    # The ad itself is clean...
    assert not any(f["severity"] in ("SPENDING", "MONEY", "BLOCKED") for f in res["findings"])
    # ...but one ad is not a campaign. A partial read-back must never read as a
    # green for the whole tree.
    assert any(f["field"] == "_coverage" for f in res["findings"]), res["findings"]
    assert res["ok"] is False


def t_audit_partial_readback_is_never_green():
    """The false green that matters: one healthy ad group, no campaign, no ads."""
    actual = {"list": [{"adgroup_id": "2", "adgroup_name": "ag-1",
                        "operation_status": "DISABLE",
                        "schedule_start_time": "2026-10-01 00:00:00"}]}
    res = mcp_mod.audit(actual)
    assert res["ok"] is False, res
    assert any(f["field"] == "_coverage" for f in res["findings"])
    assert "campaign" in res["verdict"] or "campaign" in str(res["findings"])


def t_audit_flags_ads_missing_against_spec():
    """Spec says two ads; read-back has none. Silence here loses half a launch."""
    actual = {
        "campaign": {"list": [{"campaign_id": "1", "campaign_name": "test-campaign",
                               "operation_status": "DISABLE"}]},
        "adgroups": {"list": [{"adgroup_id": "2", "adgroup_name": "ag-1",
                               "operation_status": "DISABLE"}]},
    }
    res = mcp_mod.audit(actual, base_spec(), PROFILE)
    assert not res["ok"]
    assert any(f["object"] == "ads" and f["severity"] == "MISSING" for f in res["findings"]), \
        res["findings"]


def t_audit_expect_live_inverts():
    actual = {"list": [{"ad_id": "3", "operation_status": "ENABLE"}]}
    paused = mcp_mod.audit(actual)
    assert any(f["severity"] == "SPENDING" for f in paused["findings"])
    live = mcp_mod.audit(actual, expect_paused=False)
    assert not any(f["severity"] == "SPENDING" for f in live["findings"])


def t_audit_empty_input_is_explicit():
    res = mcp_mod.audit({})
    assert not res["ok"] and "No objects found" in res["reason"]


def t_audit_flags_missing_adgroup():
    actual = {"campaign": {"list": [{"campaign_id": "1", "campaign_name": "test-campaign",
                                     "operation_status": "DISABLE"}]}}
    res = mcp_mod.audit(actual, base_spec(), PROFILE)
    assert any(f["severity"] == "MISSING" for f in res["findings"]), res["findings"]


# -- secondary status --------------------------------------------------------

def t_status_deny_is_not_review():
    # AD_STATUS_AUDIT_DENY contains "AUDIT"; naive substring matching reads a
    # rejection as a pending review.
    assert explain_status("AD_STATUS_AUDIT_DENY")["severity"] == "BLOCKED"
    assert explain_status("AD_STATUS_AUDIT")["severity"] == "REVIEW"


def t_status_longest_key_wins():
    r = explain_status("AD_STATUS_ADGROUP_INDUSTRY_QUALIFICATION_MISSING")
    assert r["matched"] == "INDUSTRY_QUALIFICATION_MISSING", r


def t_status_spark_expiry():
    r = explain_status("AD_STATUS_ASSET_AUTHORIZATION_LOST")
    assert r["severity"] == "BLOCKED" and "no grace period" in r["action"]


def t_status_handles_tiktok_typo():
    # TikTok's own enum ships AD_STAUS_PIXEL_UNBIND (sic).
    assert explain_status("AD_STAUS_PIXEL_UNBIND")["severity"] == "BLOCKED"


def t_status_balance_is_money():
    assert explain_status("AD_STATUS_BALANCE_EXCEED")["severity"] == "MONEY"


def t_status_unknown_is_flagged():
    assert explain_status("AD_STATUS_SOMETHING_NEW")["severity"] == "UNKNOWN"


def t_audit_rejection_via_status_table():
    actual = {"list": [{"ad_id": "3", "operation_status": "DISABLE",
                        "secondary_status": "AD_STATUS_AUDIT_DENY"}]}
    res = mcp_mod.audit(actual)
    assert not res["ok"], res
    assert any(f["severity"] == "BLOCKED" for f in res["findings"])





# -- regressions found by external audit, 2026-09-14 -------------------------

def t_ad_ids_are_strings_not_objects():
    """TikTok documents data.ad_ids as string[]. Treating them as dicts raised
    AttributeError *after* the ads were already created."""
    data = {"ad_ids": ["1790000000000000001", "1790000000000000002"], "need_audit": False}
    assert lifecycle.ad_ids_from_create(data) == ["1790000000000000001", "1790000000000000002"]


def t_ad_ids_tolerates_object_form_and_creatives():
    assert lifecycle.ad_ids_from_create({"ad_ids": [{"ad_id": 7}]}) == ["7"]
    assert lifecycle.ad_ids_from_create({"creatives": [{"ad_id": "9"}]}) == ["9"]
    assert lifecycle.ad_ids_from_create({}) == []


def t_partial_success_is_not_success():
    """code 20001 means some items in the batch failed. Returning data as if it
    were a clean success loses half a launch silently."""
    client = _FakeClient([{"code": 20001, "message": "partial", "data": {"ad_ids": ["1"]},
                           "request_id": "r"}])
    try:
        client.post("/ad/create/", {"advertiser_id": "1"})
    except api.PartialSuccessError as exc:
        assert exc.code == 20001
        assert exc.payload["data"]["ad_ids"] == ["1"]
    else:
        raise AssertionError("20001 was accepted as success")


def t_goal_and_billing_event_must_match():
    s = base_spec()
    s["adgroups"][0]["optimization_goal"] = "CONVERT"
    s["adgroups"][0]["billing_event"] = "CPC"      # CONVERT is billed OCPM
    s["adgroups"][0]["pixel_id"] = "p1"
    s["adgroups"][0]["optimization_event"] = "ON_WEB_ORDER"
    errs = spec_mod.validate(s, PROFILE)
    assert any("must be billed as 'OCPM'" in e for e in errs), errs


def t_billing_event_is_required():
    s = base_spec()
    del s["adgroups"][0]["billing_event"]
    assert any("billing_event is required" in e for e in spec_mod.validate(s, PROFILE))


def t_pacing_required_without_cbo_ignored_with_it():
    s = base_spec()
    del s["adgroups"][0]["pacing"]
    assert any("pacing is required" in e for e in spec_mod.validate(s, PROFILE))
    # Under CBO, TikTok overrides pacing itself, so it must not be demanded.
    s2 = cbo_spec()
    s2["adgroups"][0].pop("pacing", None)
    assert not any("pacing is required" in e for e in spec_mod.validate(s2, PROFILE))


def t_promotion_type_required_outside_exempt_objectives():
    s = base_spec()
    del s["adgroups"][0]["promotion_type"]
    assert any("promotion_type is required" in e for e in spec_mod.validate(s, PROFILE))


def t_attribution_windows_are_co_required():
    s = base_spec()
    s["adgroups"][0]["click_attribution_window"] = "SEVEN_DAYS"
    errs = spec_mod.validate(s, PROFILE)
    assert any("must be passed together" in e for e in errs), errs
    s["adgroups"][0]["view_attribution_window"] = "ONE_DAY"
    assert not any("must be passed together" in e for e in spec_mod.validate(s, PROFILE))


def t_attribution_windows_reach_the_payload():
    """A locked attribution window that never gets sent is a strategy on paper only."""
    s = base_spec()
    s["adgroups"][0]["click_attribution_window"] = "SEVEN_DAYS"
    s["adgroups"][0]["view_attribution_window"] = "OFF"
    s["adgroups"][0]["attribution_event_count"] = "EVERY"
    plan = spec_mod.normalize(s, PROFILE)
    payload = plan["adgroups"][0]["payload"]
    assert payload["click_attribution_window"] == "SEVEN_DAYS"
    assert payload["view_attribution_window"] == "OFF"
    assert payload["attribution_event_count"] == "EVERY"


def t_engaged_view_window_needs_the_other_two():
    s = base_spec()
    s["adgroups"][0]["engaged_view_attribution_window"] = "ONE_DAY"
    assert any("engaged_view_attribution_window requires" in e
               for e in spec_mod.validate(s, PROFILE))


def t_reach_and_frequency_is_refused_not_silently_broken():
    """R&F must be created ENABLED, which contradicts the create-paused guarantee.
    Refusing loudly beats emitting a payload TikTok will reject."""
    s = base_spec()
    s["campaign"]["objective_type"] = "RF_REACH"
    errs = spec_mod.validate(s, PROFILE)
    assert any("RF_REACH" in e and "not supported" in e for e in errs), errs



def t_sweep_does_not_call_a_rejection_a_review():
    """operate.sweep used the same naive substring match that errors.py fixed."""
    from .errors import explain_status
    assert explain_status("AD_STATUS_AUDIT_DENY")["severity"] == "BLOCKED"
    assert explain_status("AD_STATUS_AUDIT")["severity"] == "REVIEW"


def t_report_window_uses_the_account_timezone():
    """A Berlin machine pulling 'yesterday' for a Los Angeles account must get the
    account's yesterday, or the numbers will not match Ads Manager."""
    from . import operate
    day, resolved = operate.account_today({"timezone": "America/Los_Angeles"})
    assert resolved == "America/Los_Angeles"
    day2, resolved2 = operate.account_today({"timezone": "Pacific/Kiritimati"})
    assert resolved2 == "Pacific/Kiritimati"
    # The two zones are ~22h apart, so on most of the clock they disagree by a day.
    assert abs((day2 - day).days) <= 1
    # An unknown zone must report the fallback rather than pretend.
    _, none_resolved = operate.account_today({"timezone": "Not/AZone"})
    assert none_resolved is None


def t_get_filters_are_chunked_at_the_documented_cap():
    ids = [str(i) for i in range(250)]
    chunks = list(lifecycle._chunks(ids, lifecycle._GET_FILTER_IDS))
    assert [len(c) for c in chunks] == [100, 100, 50]
    assert sum(len(c) for c in chunks) == len(ids)


def t_every_test_in_this_file_is_registered():
    """The registry used to be built halfway down the file, so anything added below
    it was silently never run."""
    with open(__file__, encoding="utf-8") as fh:
        src = fh.read()
    defined = src.count("\ndef t_")
    collected = len([k for k in globals() if k.startswith("t_") and callable(globals()[k])])
    assert collected == defined, f"{defined} defined, {collected} collected"



def _ocpm_conversions_spec():
    """WEB_CONVERSIONS on OCPM — the shape Cost Cap validation used to get wrong."""
    s = base_spec()
    s["campaign"]["objective_type"] = "WEB_CONVERSIONS"
    ag = s["adgroups"][0]
    ag["optimization_goal"] = "CONVERT"
    ag["billing_event"] = "OCPM"
    ag["pixel_id"] = "CABC123"
    ag["optimization_event"] = "ON_WEB_ORDER"
    return s


def t_cost_cap_on_ocpm_wants_conversion_bid_price():
    """bid_price is for CPC/CPM/CPV. OCPM Cost Cap carries the bid in
    conversion_bid_price — demanding bid_price rejects a valid conversions spec, and
    accepting it sends a field TikTok does not read as the bid."""
    s = _ocpm_conversions_spec()
    s["adgroups"][0]["bid_type"] = "BID_TYPE_CUSTOM"
    errs = spec_mod.validate(s, PROFILE)
    assert any("conversion_bid_price is required" in e for e in errs), errs
    # "conversion_bid_price" ends in "bid_price" — match the start of the field name.
    assert not any(".bid_price is required" in e for e in errs), errs

    s["adgroups"][0]["conversion_bid_price"] = 12.0
    assert not [e for e in spec_mod.validate(s, PROFILE) if "bid" in e], \
        spec_mod.validate(s, PROFILE)


def t_bid_price_on_ocpm_is_rejected():
    s = _ocpm_conversions_spec()
    s["adgroups"][0]["bid_type"] = "BID_TYPE_CUSTOM"
    s["adgroups"][0]["conversion_bid_price"] = 12.0
    s["adgroups"][0]["bid_price"] = 3.0
    assert any("bid_price must be omitted when billing_event is OCPM" in e
               for e in spec_mod.validate(s, PROFILE))


def t_conversion_bid_price_on_cpc_is_rejected():
    s = base_spec()          # CLICK / CPC
    s["adgroups"][0]["bid_type"] = "BID_TYPE_CUSTOM"
    s["adgroups"][0]["bid_price"] = 0.5
    s["adgroups"][0]["conversion_bid_price"] = 12.0
    assert any("conversion_bid_price applies to OCPM only" in e
               for e in spec_mod.validate(s, PROFILE))


def t_ocpm_bid_reaches_the_payload():
    s = _ocpm_conversions_spec()
    s["adgroups"][0]["bid_type"] = "BID_TYPE_CUSTOM"
    s["adgroups"][0]["conversion_bid_price"] = 12.0
    payload = spec_mod.normalize(s, PROFILE)["adgroups"][0]["payload"]
    assert payload["conversion_bid_price"] == 12.0
    assert "bid_price" not in payload



def t_smart_plus_and_gmv_max_are_refused():
    """Both have their own endpoints. Emitting an ordinary payload creates a
    different product than the one that was planned."""
    s = base_spec()
    s["campaign"]["campaign_type"] = "SMART_PERFORMANCE_CAMPAIGN"
    assert any("does not build Smart+" in e for e in spec_mod.validate(s, PROFILE))

    s2 = base_spec()
    s2["campaign"]["objective_type"] = "PRODUCT_SALES"
    s2["campaign"]["campaign_product_source"] = "STORE"
    assert any("does not build GMV Max" in e for e in spec_mod.validate(s2, PROFILE))


def t_qpm_backoff_respects_the_documented_five_minutes():
    """A 20-second first retry on 40100 re-offends inside TikTok's penalty window."""
    c = Client(token="x", allow_writes=False)
    wait = c._backoff(0, True, 40100)
    assert wait >= 300.0, wait
    # Per-advertiser throttling is about serialising, not a flat penalty.
    assert c._backoff(0, True, 40133) < 300.0


def t_doctor_status_table_matches_the_enum():
    only_ok = [k for k, v in lifecycle.ADVERTISER_STATUS.items() if v == "OK"]
    assert only_ok == ["STATUS_ENABLE"], only_ok
    assert lifecycle.ADVERTISER_STATUS["STATUS_LIMIT"] == "PUNISHED"
    assert lifecycle.ADVERTISER_STATUS["STATUS_DISABLE"] == "CLOSED"
    assert set(lifecycle.ADVERTISER_STATUS) == set(lifecycle.ADVERTISER_STATUS_TEXT)



# -- field-level drift: a full read-back that lies ---------------------------

def _locked_spec():
    """A spec whose attribution window and destination are deliberate decisions."""
    s = base_spec()
    ag = s["adgroups"][0]
    ag["click_attribution_window"] = "SEVEN_DAYS"
    ag["view_attribution_window"] = "OFF"
    ag["video_download_disabled"] = True
    return s


def _full_readback(**overrides):
    ag = {"adgroup_id": "2", "adgroup_name": "ag-1", "operation_status": "DISABLE",
          "optimization_goal": "CLICK", "billing_event": "CPC",
          "bid_type": "BID_TYPE_NO_BID", "budget_mode": "BUDGET_MODE_DAY", "budget": 50,
          "placement_type": "PLACEMENT_TYPE_AUTOMATIC", "promotion_type": "WEBSITE",
          "pacing": "PACING_MODE_SMOOTH", "schedule_type": "SCHEDULE_FROM_NOW",
          "schedule_start_time": "2026-09-20 07:00:00",
          "click_attribution_window": "SEVEN_DAYS", "view_attribution_window": "OFF",
          "video_download_disabled": True}
    ad = {"ad_id": "3", "adgroup_id": "2", "ad_name": "ad-1",
          "operation_status": "DISABLE", "ad_format": "SINGLE_VIDEO",
          "identity_type": "CUSTOMIZED_USER", "video_id": "v1",
          "landing_page_url": "https://example.com"}
    ag.update(overrides.pop("adgroup", {}))
    ad.update(overrides.pop("ad", {}))
    return {"campaign": {"list": [{"campaign_id": "1", "campaign_name": "test-campaign",
                                   "operation_status": "DISABLE",
                                   "objective_type": "TRAFFIC",
                                   "budget_mode": "BUDGET_MODE_DAY", "budget": 100,
                                   "special_industries": []}]},
            "adgroups": {"list": [ag]},
            "ads": {"list": [ad]}}


def t_honest_full_readback_is_green():
    res = mcp_mod.audit(_full_readback(), _locked_spec(), PROFILE)
    assert res["ok"] is True, res["findings"]


def t_changed_attribution_window_blocks():
    """Attribution is permanent once set. A silent change is unfixable later."""
    res = mcp_mod.audit(_full_readback(adgroup={"click_attribution_window": "ONE_DAY"}),
                        _locked_spec(), PROFILE)
    assert res["ok"] is False
    assert any(f["field"] == "click_attribution_window" and f["severity"] == "DRIFT"
               for f in res["findings"]), res["findings"]


def t_changed_destination_url_blocks():
    """The ad is where the money points. An unchecked URL sends spend elsewhere."""
    res = mcp_mod.audit(_full_readback(ad={"landing_page_url": "https://attacker.example"}),
                        _locked_spec(), PROFILE)
    assert res["ok"] is False
    assert any(f["field"] == "landing_page_url" and f["severity"] == "DRIFT"
               for f in res["findings"]), res["findings"]


def t_changed_creative_asset_blocks():
    res = mcp_mod.audit(_full_readback(ad={"video_id": "v-other"}), _locked_spec(), PROFILE)
    assert any(f["field"] == "video_id" and f["severity"] == "DRIFT"
               for f in res["findings"]), res["findings"]


def t_changed_identity_blocks():
    """Whose account the ad posts from. A swapped identity is a different advertiser
    in the viewer's feed."""
    spec = _locked_spec()
    spec["adgroups"][0]["creatives"][0].update(identity_type="TT_USER",
                                               identity_id="tt-account-1")
    actual = _full_readback(ad={"identity_type": "TT_USER", "identity_id": "someone-else"})
    res = mcp_mod.audit(actual, spec, PROFILE)
    assert any(f["field"] == "identity_id" and f["severity"] == "DRIFT"
               for f in res["findings"]), res["findings"]


def t_changed_conversion_bid_price_blocks():
    s = _ocpm_conversions_spec()
    s["adgroups"][0]["bid_type"] = "BID_TYPE_CUSTOM"
    s["adgroups"][0]["conversion_bid_price"] = 12.0
    actual = _full_readback(adgroup={"optimization_goal": "CONVERT", "billing_event": "OCPM",
                                     "bid_type": "BID_TYPE_CUSTOM",
                                     "conversion_bid_price": 99.0,
                                     "pixel_id": "CABC123",
                                     "optimization_event": "ON_WEB_ORDER"})
    res = mcp_mod.audit(actual, s, PROFILE)
    assert any(f["field"] == "conversion_bid_price" and f["severity"] == "DRIFT"
               for f in res["findings"]), res["findings"]


def t_unreported_field_is_unconfirmed_not_silence():
    """A field the platform does not echo is neither verified nor drift. It must be
    visible — several of these are permanent — without blocking every run."""
    actual = _full_readback()
    del actual["adgroups"]["list"][0]["click_attribution_window"]
    res = mcp_mod.audit(actual, _locked_spec(), PROFILE)
    assert any(f["field"] == "click_attribution_window" and f["severity"] == "UNCONFIRMED"
               for f in res["findings"]), res["findings"]
    assert res["worst_severity"] == "UNCONFIRMED"


def t_ad_not_in_the_spec_is_flagged():
    actual = _full_readback(ad={"ad_name": "ad-nobody-planned"})
    res = mcp_mod.audit(actual, _locked_spec(), PROFILE)
    assert any(f["field"] == "_unexpected" for f in res["findings"]), res["findings"]


def t_http_429_is_treated_as_throttling():
    """TikTok is not documented to send 429; a proxy in front of it can."""
    sleeps = []

    class _Fake429(Client):
        def __init__(self):
            # `sleep` is injected on the instance, so overriding the method would be
            # shadowed — and the test would really sleep for five minutes.
            super().__init__(token="x", allow_writes=False, max_retries=1,
                             sleep=sleeps.append)
            self.n = 0

        def _request(self, method, path, params=None, body=None):
            self.n += 1
            if self.n == 1:
                return {"code": 40100, "message": "rate limited"}, 429
            return {"code": 0, "data": {"ok": True}}, 200

    c = _Fake429()
    c.sleeps = sleeps
    assert c.get("/campaign/get/") == {"ok": True}
    assert c.sleeps and c.sleeps[0] >= 300.0, c.sleeps


def t_create_without_an_id_fails_loudly():
    """Recording None means a re-run thinks the object exists and skips it."""
    raises(RuntimeError,
           lambda: lifecycle._require_id({"code": 0}, "campaign_id", "/campaign/create/"),
           "no campaign_id")
    assert lifecycle._require_id({"campaign_id": 17}, "campaign_id", "/x/") == "17"


def main():
    # Collected here, not at import time: a registry built halfway down the file
    # silently drops every test added below it.
    tests = [(k[2:], v) for k, v in sorted(globals().items())
             if k.startswith("t_") and callable(v)]
    for name, fn in tests:
        check(name, fn)
    print(f"ttops selftest: {len(PASS)} passed, {len(FAIL)} failed")
    for failure in FAIL:
        print("  FAIL " + failure)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
